import os
import datetime 

from google.appengine.dist import use_library
use_library('django', '1.0')
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from django.utils import simplejson

import emails
import googlecheckout
import models
import settings

def create_error_query_string(errors):
    "return a url query string with a string of errors"
    query_string = ''
    split_string = split_notification_string(errors, '-')
    for error in split_string:
        if len(query_string) == 0:
            query_string += 'errors=%s' % str(error)
        else: query_string += '.%s' % str(error)
    return query_string

def get_tag_list(tag_dict):
    "Convert tag dict to a list."
    tag_list = []
    for tag in tag_dict.keys(): tag_list.append(tag)
    return tag_list  

def split_notification_string(error, separator):
    "split a string using the given separator"
    error_string = str(error)
    error_string.strip() #remove whitespace
    split_string = error_string.split(separator)
    return split_string

class BaseRequestHandler(webapp.RequestHandler):
    def __init__(self):
        self.session = False
        self.user_google = users.get_current_user()
        self.template_values = { 'admin' : users.is_current_user_admin(), 'tag_dict' : models.Tag.get_tag_dict() }
         
    def initialize(self, request, response):
        "Initialize webapp, so that we can use the request method to get the session." 
        webapp.RequestHandler.initialize(self, request, response)
        self.session = models.Session.get_session(request.cookies.get('uid',''))

        if self.session is not None:
            self.session = self.session.check_for_google_login(self.user_google)
        elif self.user_google: #no session and user has logged in, so we need to create session
            self.session = models.Session.create_session(self.user_google)
        return
               
    def check_for_notifications(self, error_or_notices, string_list):
        """Check the query string for specific errors or notices. 
           Args: 'error' or 'notice', string list of errors or notices to check for."""
        string = self.request.get(error_or_notices)
        if string:
            split_string = split_notification_string(string, '-')
            notification_list = [] #only use nofications that we want
            for x in split_string:
                if x in string_list: notification_list.append(x)
            self.update_template_notifications(error_or_notices, notification_list)
        return
    
    def add_template_values(self):
        "Add user login values and values from settings to template dict"
        if self.user_google: 
            url = users.create_logout_url(self.request.uri)
            url_link_text = 'Google Logout'
        else: 
            url = users.create_login_url(self.request.uri)
            url_link_text = 'Google Login' 
        
        values = {
                  'google_analytics_account' : settings.GOOGLE_ANALYTICS_ACCOUNT,
                  'merchant_id' : settings.MERCHANT_ID,
                  'site_name' : settings.SITE_NAME,
                  'tag_name' : settings.TAG_NAME,
                  'url': url,
                  'url_link_text': url_link_text,
                  }
        self.template_values.update(values)
        
    def generate(self, template_name, template_values):
        "create page with template name and template values"
        #update template values with template values from self
        self.add_template_values()
        template_values.update(self.template_values)

        if 'popular_products' not in template_values: 
            template_values.update({ 'popular_products' : models.get_popular_products() })
        template_values.update({'tag_dict' : self.template_values['tag_dict'].items()})
        
        if self.session is not None:
            if 'number_cart_items' in self.session:
                if self.session['number_cart_items'] > 0:
                    template_values.update({'number_cart_items' : self.session['number_cart_items']})
            if self.session.cookie: #set the session cookie if it exists 
                self.response.headers['Set-cookie'] = str(self.session.cookie)
            if self.session['updated']: 
                self.session.put() #put the updated session
        expires_date = datetime.datetime.utcnow() + datetime.timedelta(1)
        expires_str = expires_date.strftime("%d %b %Y %H:%M:%S GMT")
        self.response.headers.add_header("Expires", expires_str)
        path = os.path.join(os.path.dirname(__file__),template_name)
        self.response.out.write(template.render(path, template_values))
  
    def generate_error(self, error_code, template_values={}):
        self.error(error_code)
        self.add_template_values()
        template_values.update(self.template_values)
        template_values.update({'page_title' : settings.SITE_NAME + ' - Oops' , 'no_sidebar' : True })
        template_name = 'templates/error.html'
        path = os.path.join(os.path.dirname(__file__),template_name)
        self.response.out.write(template.render(path, template_values))

    def handle_exception(self, *args):
        import sys
        import traceback
        import logging
        error_text = ''.join(traceback.format_exception(*sys.exc_info()))
        logging.error(error_text)
        emails.mail_admin(error_text, "Exception")
        template_values = {}
        if users.is_current_user_admin(): template_values['traceback'] = error_text
        else: template_values['traceback'] = settings.SITE_DOWN_MESSAGE
        self.generate_error(500, template_values = template_values)
        
    def get(self, *args): pass               
    def post(self, *args): pass

    def update_template_notifications(self, errors_or_notices, string_list):
        "Update template with errors or notices. Match the string list with the dict from the settings file."
        notification_list = []
        if errors_or_notices == 'errors': dict = settings.ERROR_DICT
        else: dict = settings.NOTICE_DICT
        for string in string_list:
            notification_list.append(dict[string])
        self.template_values.update({ errors_or_notices : notification_list })
        return
    
class BaseFileHandler(webapp.RequestHandler):
    def get(self, *args): pass                   
    def post(self, *args): pass
    def file_response_output(self, entity):
        if entity.file_type == 'gif' or entity.file_type == 'jpg' or entity.file_type == 'png': 
            header_type = 'image'
        else:
            header_type = 'application'
        if entity.file_type == 'doc': file_type = 'msword'
        else: file_type = str(entity.file_type)
        self.response.headers['Content-Type'] = '%s/%s' % (header_type, file_type)
        file_data_key = models.ProductFile.file.get_value_for_datastore(entity)
        file_data = db.get(file_data_key) #get the actual data
        self.response.out.write(file_data.data)

    def generate_error(self, error_code, template_values={}):
        self.error(error_code)
        template_values.update({'page_title' : settings.SITE_NAME + ' - Oops' , 'no_sidebar' : True })
        template_name = 'templates/error.html'
        path = os.path.join(os.path.dirname(__file__),template_name)
        self.response.out.write(template.render(path, template_values))

class AdminHandler(BaseRequestHandler):
    "handler for admin allowing for model views"
    def get(self, page):
        if self.template_values['admin']:
            if page == 'flush_memcache':
                try: memcache.flush_all()
                except: print 'Unable to clear memcache'
                self.redirect('/admin/home')
            else:
                self.check_for_notifications('notices', ['item_used'])
                model_name = self.request.get('item')
                if not model_name: model_name = 'products'
                pagination = models.Pagination()
                template_values = pagination.get_values(self.request, model_name, None, is_admin=True)
                if not template_values: self.generate_error(404)
                else: 
                    self.template_values.update(template_values)
                    self.generate('templates/admin.html', { 'page_title' : 'Admin', 'no_sidebar' : True })              
        else: self.generate_error(403)

class PaidFileHandler(BaseRequestHandler, BaseFileHandler):
    """Handler to serve paid for files from the datastore.
       args: file_id"""
    def get(self, file_id):
        #if user is not logged in and doesn't have a session, we don't allow access
        if not self.user_google and not self.session:
            self.generate_error(404)
            return
        try: 
            file_id = int(file_id)
            file = models.ProductFile.get_by_id(file_id)
        except: file = None
        if file:   
            if self.template_values['admin']: is_product_purchased = True
            else: is_product_purchased = self.session.is_product_purchased(models.ProductFile.product.get_value_for_datastore(file))
            if is_product_purchased:
                self.file_response_output(file) #set response headers
            else: self.generate_error(403)
        else: self.generate_error(404)

class FreeFileHandler(BaseFileHandler):
    "to serve free files/images from the datastore"
    def get(self, file_id):
        try:
            file = memcache.get(file_id, namespace='files')
            if not file: 
                file_id = int(file_id)
                file = models.ProductFile.get_by_id(file_id)
                try: memcache.add(file_id, file, namespace='files')
                except: pass
        except: file = None
        if file:
            if file.content_type == 'pay': #not a free file!
                self.generate_error(403)
            else: 
                self.file_response_output(file)
        else: self.generate_error(404)

class UploadHandler(BaseRequestHandler):
    "To upload a new file or image from product view page" 
    def get(self, file_type, product_key):
        if users.is_current_user_admin():   
            if product_key and file_type: #get the product key to send to POST
                if file_type == 'image' or file_type == 'file':
                    post_url = '/upload/' + str(file_type) + '/' + str(product_key)
                    self.generate('templates/upload.html', {
                                                            file_type : file_type,
                                                            'no_sidebar' : True,
                                                            'page_title' : 'New ' + str(file_type),
                                                            'post_url' : post_url,
                                                            })
                else: self.generate_error(404) 
            else: self.generate_error(404)
        else: self.generate_error(404)
  
    def post(self, file_type, product_key):
        "Create a new file."
        if users.is_current_user_admin():
            product = models.Product.get(product_key)
            if product:
                #collect file data
                data = self.request.POST.get('data').file.read()
                #if file data exists add it to the product
                if data:
                    file_type = self.request.get('file_type')
                    content_type = self.request.get('content_type')
                    try:
                        file = models.FileData(data = data)
                        file.put() #put the actual data
                        product_file = models.ProductFile(file = file, content_type = content_type, file_type = file_type, product = product)
                        product_file.put()
                    except: print 'upload failed, try again.'
                    product.files.append(product_file.key()) #add to file key list
                    product.files = product.verify_file_list()
                    product.put()
                    self.redirect('/products/%s/%s' % (product.key().id(), models.slugify(product.title)))
                else: print 'No file uploaded'
            else: print 'No product found'
        else: self.generate_error(403)
                      
class UserHandler(BaseRequestHandler):
    """    Handler for shopping cart, my purchased products, and checkout
           Session are created for users when they access this handler  """      
    def get(self, page_name):
        if self.session is None: #create session
            self.session = models.Session.create_session(self.user_google)

        if page_name == 'cart':
            self.check_for_notifications('errors', ['quantity', 'google_post'])
            cart_products = self.session.get_cart_products()
            total_price = self.session.calculate_total(cart_products=cart_products) #calculate the cart total price
            self.generate('templates/cart.html', {
                                                  'page_title' : 'Shopping Cart',
                                                  'popular_products' : False,                                            
                                                  'products' : cart_products,
                                                  'total_price' : total_price,
                                                  'no_sidebar' : True,
                                                  })
                            
        elif page_name == 'home':
            self.check_for_notifications('errors', ['email', 'email_limit', 'key'])
            self.check_for_notifications('notices', ['purchase', 'email'])
            purchase_key_name = self.request.get('key')
            if purchase_key_name:
                try:
                    purchase = models.Purchase.get_by_key_name(purchase_key_name)
                    self.session.add_purchase(purchase) #add this purchase to the list of session purchases
                    self.redirect('/user/home?notices=purchase')
                    return
                except:    
                    self.redirect('/user/home?errors=key')
                    return
            if self.template_values['admin']: #admin sees all files
                data_query = models.Product.all()
                pagination = models.Pagination()
                template_values = pagination.get_values(self.request, 'products', data_query, is_admin=True)
                template_values['products'] = models.prefetch_product_files(template_values['products']) #prefetch files
                self.template_values.update(template_values)
            else:
                purchased_products = self.session.get_purchased_products()
                self.template_values.update({ 'products' : purchased_products }) #admin already adds this to the template
            self.generate('templates/user.html', {
                                                  'page_title' : 'User Account',                                            
                                                  'no_sidebar' : True,  
                                                  })
        elif page_name == 'checkout':
            total_price = self.session.calculate_total()
            if 0 < total_price:
                redirect_url = googlecheckout.post_shopping_cart(self.session)        
                if redirect_url: self.redirect(redirect_url)
                else:
                    emails.mail_user(settings.SITE_EMAIL, 'Google Post Shopping Cart Error', 'Admin Error')
                    self.redirect('/user/cart?errors=google_post')
            else:
                self.redirect('/user/cart')
              
        else: self.generate_error(404)
               
    def post(self, page_name):
        "Modify cart contents, update user purchase keys, send reminder emails" 
        if self.session is None: #create session
            self.session = models.Session.create_session(self.user_google)
            #set the cookie since we won't be setting it through the generate function
            self.response.headers['Set-cookie'] = str(self.session.cookie)
                   
        if page_name == 'cart':
            action = self.request.POST.get('action')
            if action == 'add':
                product_key = self.request.POST.get('product_key')
                try: 
                    self.session.add_to_cart(product_key, 1) #only allow for one item adding via add to cart
                    self.redirect('/user/cart')
                except (Exception), errors:
                    self.redirect('/user/cart?' + create_error_query_string(errors))
                return
                    
            elif action == 'update':
                errors = []
                #update button was clicked so update cart items    
                item_keys = self.request.get_all('item_key')
                quantities = self.request.get_all('quantity')
                try: 
                    self.session.update_cart(item_keys, quantities)
                    self.redirect('/user/cart')
                except (Exception), errors:
                    self.redirect('/user/cart?%s' % create_error_query_string(errors))
                    
            elif action == 'remove':
                product_key = self.request.get('remove_key')
                #remove button clicked so remove item from cart
                self.session.remove_from_cart(product_key)
                self.redirect('/user/cart')    
              
            else: self.generate_error(404)
                                
        elif page_name == 'home': # for adding user keys to session
            purchase_key_name = self.request.POST.get('key')
            try:
                purchase = models.Purchase.get_by_key_name(purchase_key_name)
                #add this purchase to the list of session purchases
                self.session.add_purchase(purchase)
                self.redirect('/user/home?notices=purchase')
            
            except:    
                self.redirect('/user/home?errors=key')

        elif page_name == 'reminder':
            purchase_email = self.request.POST.get('email')
            if purchase_email:
                purchases = models.Purchase.all().filter('email =', purchase_email).fetch(settings.SAFE_FETCH_NUMBER)
                if not purchases: self.redirect('/user/home?errors=email')
                else: #only email user max 1 time per day
                    purchase_keys = [ str(x.key()) for x in purchases ]
                    error = emails.mail_user_reminder(purchase_email, purchase_keys)
                    if error:
                        self.redirect('/user/home?errors=email_limit')
                    else:
                        self.redirect('/user/home?notices=email')
            else: self.redirect('/user/home?errors=email')    
            
        else: self.generate_error(404)

class SearchHandler(BaseRequestHandler):
    def get(self):
        model_dict = { 'pages' : models.Page, 'products' : models.Product, 'tags' : models.Tag }
        search_string = self.request.get('q')
        model_name = self.request.get('item')
        if not model_name: model_name = 'products'
        try: 
            data = model_dict[model_name].search(search_string)
        except: 
            self.generate_error(404)
            return
        self.generate('templates/list.html', { 
                                              model_name : data,
                                              'page_title' : 'Search - ' + model_name,
                                              'search' : True,
                                              })
        
class PageHandler(BaseRequestHandler):
    "For all page view requests."
    def get(self, page_name):
        if page_name == '': page_name = 'home' #set the homepage
        retrieved_from_memcache = True
        page = memcache.get(models.slugify(page_name), namespace='pages')
        if not page:
            retrieved_from_memcache = False
            page = models.Page.all().filter('url =', models.slugify(page_name)).get() 
        if not page: 
            if self.template_values['admin']: #prefill the title if we have a page_name
                self.redirect('/edit?action=new&id=%s&item=page' % (page_name)) 
                return
            else:    
                self.generate_error(404)
        else: #standard page view
            if not retrieved_from_memcache: 
                try: memcache.add(models.slugify(page_name), page, namespace='pages')
                except: pass
            self.generate('templates/view.html', { 
                                                  'page_title' : page.title,
                                                  'data' : page,
                                                  })       
        
class ProductHandler(BaseRequestHandler):
    def get(self, product_id, product_title):  
        template_values = memcache.get(product_id, namespace='products')
        if not template_values:
            product = models.Product.get_by_id(int(product_id))
            if not product:
                self.generate_error(404)
                return
            #make sure the product page title is the same as the title in the datastore
            if not str(product_title) == models.slugify(product.title):
                self.generate_error(404)
                return
            if not product.active and not self.template_values['admin']: #only admin can see non-active
                self.generate_error(404)
                return    
            #retrieve files and images so that they can be stored in the memcache too
            all_files = models.ProductFile.get(product.files)
            pay_files = []
            free_files = []
            image_files = []
            for file in all_files:
                if file.content_type == 'pay': pay_files.append(file)
                elif file.content_type == 'free': free_files.append(file)
                else: image_files.append(file)
            template_values = {
                               'all_files' : all_files,
                               'data' : product,
                               'file_types' : settings.PAY_FILE_TYPES,
                               'free_files' : free_files,
                               'image_files' : image_files,
                               'page_title' : product.title,
                               'pay_files' : pay_files,
                               'purchase_days' : settings.PURCHASE_DAYS, 
                               }
            
            try: memcache.add(product_id, template_values, namespace='products')
            except: pass
        if not self.template_values['admin']: #increase page view counter
            memcache.incr(product_id, namespace='counters', initial_value=0)         
        self.template_values.update(template_values)
        if not self.template_values['admin'] and self.session:
            product = self.template_values['data'] #get product to test if purchased
            is_product_purchased = self.session.is_product_purchased(product.key())
            self.template_values.update({ 'is_product_purchased' : is_product_purchased })
        self.generate('templates/view.html', {})
                
class TagHandler(BaseRequestHandler):
    """Handler to display all products and to display all products matching 1 tag. Data should not be stored
       in memcache for too long, because there is no way to update if there are data changes."""
    def get(self, url_tag):
        all_tags = get_tag_list(self.template_values['tag_dict']) #get tags and only display tags that aren't in url
        safe_tags = []
        if url_tag in all_tags: #only add in tags that match from the complete tag list
            safe_tags.append(url_tag)
        #for tag in safe_tags:
        #    all_tags = all_tags.remove(tag)
        query = models.Product.all()
        if safe_tags:
            for tag in safe_tags:
                query.filter('tags =', tag)
        pagination = models.Pagination() #get pagination values including products
        template_values = pagination.get_values(self.request, 'products', query)
        if not template_values: 
            self.generate_error(404)
            return
        if url_tag: page_title = url_tag
        else: page_title = 'All Products'
        template_values.update({ 'page_title' : page_title })
        self.template_values.update(template_values) 
        self.generate('templates/list.html', {})

class EditHandler(BaseRequestHandler):
    model_dict = { 'file' : models.ProductFile, 'page' : models.Page, 'product' : models.Product, 'purchase' : models.Purchase, 'user' : models.User }
    model_form_dict = { 'page' : models.PageForm, 'product' : models.ProductForm, 'purchase' : models.PurchaseForm, 'user' : models.UserForm }
    
    def add_purchase_values(self, purchase=False):
        """Add products and default products associated with this purchase (if given) to the template.
           Kwargs: purchase entity"""
        products = models.Product.all().fetch(1000)
        self.template_values.update({ 'products' : products, 'purchase' : True })
        if purchase: #add default items if they are already in purchase
            purchase_items = [ x for x in purchase.items ]
            if purchase_items:
                purchase_items = models.prefetch_refprops(purchase_items, models.PurchaseItem.product)
                default_products = []
                for purchase_item in purchase_items:
                    #product_key = models.PurchaseItem.product.get_value_for_datastore(purchase_item) 
                    for product in self.template_values['products']:
                        if purchase_item.product.key() == product.key():
                        #if product_key == product.key(): #check product key from PurchaseItem with product keys in list
                            self.template_values['products'].remove(product)
                            default_products.append(purchase_item.product)
                self.template_values.update({ 'default_products' : default_products })
        return
    
    def build_post_url(self, action, model, id):
        "method to build post urls"
        post_url = models.build_url({ 'action' : action, 'item' : model, 'id' : id }, url = '/edit')
        return post_url
    
    def build_redirect_url(self, entity, model):
        "method to build redirect url after successful post"
        if model == 'product': 
            redirect_url = '/products/%s/%s' % (str(entity.key().id()), models.slugify(entity.title))
        elif model == 'page': redirect_url = entity.url
        else: redirect_url = '/admin/home?item=%ss' % (model)
        return redirect_url
    
    def build_delete_data(self, entity, model):
        "returns data to be displayed to admin before deleting"
        data = ''
        attribute_value_list = [(prop, getattr(entity, prop)) for prop in self.model_dict[model].properties()]
        for attribute, value in attribute_value_list:
            data += '<div><b>%s :</b> %s</div>\n' % (str(attribute), str(value))
        return data
    
    def generate_edit_form(self, data, model, page_title, post_url, template, entity=False):
        "method to generate edit and delete form"
        if model == 'product':
            template_values = { 'json_tags' : simplejson.dumps(get_tag_list(self.template_values['tag_dict']))}
            if entity: #only add in tags if this is not a new product
                template_values.update({'tags_as_string' : models.Tag.get_tags_as_string(entity.tags)})
            self.template_values.update(template_values)
        elif model == 'purchase':
            self.add_purchase_values(entity)
        self.generate( template , {
                                    'data' : data,
                                    'page_title' : page_title,
                                    'post_url' : post_url,
                                    'no_sidebar' : True,  
                                    })
        
    def get_entity(self, model, id):
        if model == 'user' or model == 'purchase': entity = self.model_dict[model].get_by_key_name(id)
        else: entity = self.model_dict[model].get_by_id(int(id))
        return entity
        
    def get(self):
        if self.template_values['admin']:
            action = self.request.get('action') #new, delete, and edit if none   
            model = self.request.get('item') #page, product, purchase model
            id = self.request.get('id') #entity id for purchases and title for pages
            post_url = self.build_post_url(action, model, id)
            if action == 'new':
                if id: data = models.PageForm(initial={'title' : id }) #pre-populate title if this is a redirect from a non-existent page
                else: data = self.model_form_dict[model]()
                post_url = self.build_post_url(action, model, id)
                if model == 'product':
                    json_tags = simplejson.dumps(get_tag_list(self.template_values['tag_dict']))
                    self.template_values.update({ 'json_tags' : json_tags }) #only needed for product model
                elif model == 'purchase': 
                    self.add_purchase_values()
                self.generate( 'templates/edit.html' , {
                                                        'data' : data,
                                                        'page_title' : 'New ' + model.capitalize(),
                                                        'post_url' : post_url,
                                                        'no_sidebar' : True,
                                                        })
            else:
                try: entity = self.get_entity(model, id)
                except: entity = None
                if not entity:
                    self.generate_error(404)
                    return
                if not action:
                    data = self.model_form_dict[model](instance=entity)
                    page_title = 'Edit'
                    template = 'templates/edit.html'
                elif action == 'delete':
                    page_title = 'Delete'
                    if model == 'user':
                        data = self.build_delete_data(entity, model)
                        self.template_values.update({ 'delete_built_data' : True })
                    elif model == 'file': #delete file through GET method, delete product memcache as well
                        product = models.Product.all().filter('files =', entity.key()).get()
                        product.files.remove(entity.key())
                        product.put()
                        redirect_url = self.build_redirect_url(product, 'product')
                        entity.delete()
                        self.redirect(redirect_url)
                        return
                    elif model == 'product': 
                        self.check_for_notifications('errors', ['product_purchased']) 
                        data = entity
                    elif model == 'purchase':
                        data = self.build_delete_data(entity, model)
                        self.template_values.update({ 'delete_built_data' : True })
                    else: data = entity
                    template = 'templates/delete.html'
                else:
                    self.generate_error(403)
                    return
                self.generate_edit_form(data, model, page_title, post_url, template, entity=entity)  
                
        else: self.generate_error(403) #not admin
    
    def post(self):
        if self.template_values['admin']:
            action = self.request.get('action')   
            model = self.request.get('item') 
            id = self.request.get('id') #entity id for purchases and title for pages
            post_url = self.build_post_url(action, model, id)
            if action == 'new':
                entity = False
                page_title = 'New ' + model.capitalize() 
                data = self.model_form_dict[model](data=self.request.POST)
            else:
                entity = self.get_entity(model, id)
                if not entity:
                    self.generate_error(404)
                    return
                if model == 'product': 
                    old_tag_list = entity.tags #keep copy of old tags
                    original_product_status = entity.active #keep copy of original active status
                    original_title = entity.title
                if not action:
                    page_title = 'Edit'
                    data = self.model_form_dict[model](data=self.request.POST, instance=entity)
                elif action == 'delete':
                    redirect_url = '/admin/home?item=%ss' % (model)
                    if model == 'product': #make sure entity is not purchased before deleting
                        is_entity_purchased = entity.is_entity_purchased()
                        if is_entity_purchased:
                            redirect_url = '/edit?action=delete&item=product&id=%s' % str(entity.key().id())
                            self.redirect(redirect_url + '&errors=product_purchased')
                            return
                        else:
                            models.update_popular_products()
                    entity.delete()
                    self.redirect(redirect_url)
                    return
                else: 
                    self.generate_error(400)
                    return

            data_valid = data.is_valid()
            if data_valid: #check the to make sure the data is valid 
                entity = data.save(commit=False)
                if model == 'product': 
                    product_tags = self.request.POST.get('tags')
                    new_tag_list = models.Tag.clean_tags(product_tags, ',')
                    entity.tags = new_tag_list
                elif model == 'page': # for pages slugify the title for the url
                    entity.url = '%s' % (models.slugify(entity.title))
                elif model == 'purchase': #for purchases
                    product_id_add_list = self.request.get_all('product_ids')
                    email = entity.purchase_email
                    user = models.User().all().filter('email =', email).get()
                    if user:
                        user.delete_sessions() #delete current user session, so purchases get updated
                        entity.user = user
                    if action == "new":
                        key_name = models.generate_purchase_key()
                        entity.purchase_id = int(key_name.split('-')[0])
                        entity = models.Purchase(key_name = key_name, **dict([(prop, getattr(entity, prop)) for prop in models.Purchase.properties()]))
                entity.put()
                if model == 'product': 
                    need_update_popular_products = False
                    try: entity.index()
                    except: print 'indexing failed - at least one tag is required'
                    if action == 'new': 
                        old_tag_list = [] #no tags for new product
                        need_update_popular_products = True
                    else:
                        if not entity.active == original_product_status or not entity.title == original_title: 
                            need_update_popular_products = True
                    if not new_tag_list == old_tag_list: 
                        models.Tag.update_tags(new_tag_list, old_tag_list, entity)
                        need_update_popular_products = True
                    if need_update_popular_products: models.update_popular_products()
                elif model == 'purchase':
                    if product_id_add_list:
                        entity.admin_add_purchase_items(entity.charge_date, product_id_add_list, user, entity.total_charge_amount)
                self.redirect(self.build_redirect_url(entity, model))
            
            else:
                template = 'templates/edit.html'
                self.generate_edit_form(data, model, page_title, post_url, template, entity=entity)