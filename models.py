import Cookie
import datetime
import uuid
import pickle

from google.appengine.dist import use_library
use_library('django', '1.0')
from google.appengine.ext import db
from google.appengine.datastore import entity_pb #for serializing and deserializing memcache adds/gets
from google.appengine.ext.db import djangoforms
from google.appengine.api import memcache
from django import forms
from django.forms.util import ErrorList

import settings
# The following are necessary for full-text search demo
import search
INDEXING_URL = '/tasks/searchindexing'

def build_string_from_list(list, separator):
    "Return string from list using the string separator."
    result = ''
    for string in list:
        if len(result) == 0: result = string
        else: result = '%s%s%s' % (result, separator, string)
    return result

def build_url(query_string_dict, url=''):
    "for building urls by giving a query string dict as an argument"
    query_string = ''
    for string in query_string_dict:
        if query_string_dict[string]: #make sure there is a value for the dict key
            if len(query_string) == 0: url += '?'
            else: query_string += '&'
            query_string += '%s=%s' % (string, query_string_dict[string])
    url += query_string
    return url

def generate_purchase_key():
    "for generating a unique key for new Purchase"
    key = str(uuid.uuid4())
    key = key.replace("-","")
    key = '%s-%s' % (get_new_id(), key[0:12])
    get_new_id()
    return key

def generate_session_key():
    "for generating a unique key for new Session"
    key = str(uuid.uuid4())
    key = key.replace("-","")
    return key

def get_new_id():
    'get the last id for Purchase Model'
    query = Purchase.all()
    query.order('-purchase_id')
    last_item = query.get()      
    #if no earlier cart or purchase then we make the id equal 1
    try: id = last_item.purchase_id + 1
    except: id = settings.PURCHASE_ID_START
    return id

def get_popular_products():
    popular_products = memcache.get("popular_products")
    if popular_products is not None:
        try: return deserialize_entities(popular_products)
        except: pass
    popular_products = update_popular_products()
    return popular_products

def update_popular_products():
    popular_products = Product.all().order('-views').filter("active =", True).fetch(settings.NUMBER_POPULAR_PRODUCTS)
    try: memcache.set("popular_products", serialize_entities(popular_products)) #set memcache
    except: pass
    return popular_products

#from Nick Johnson's blog - http://blog.notdot.net/2010/01/ReferenceProperty-prefetching-in-App-Engine
def prefetch_refprops(entities, *props):
    """Prevents multiple queries for the same referenceproperty and gets all the ref props in one db.get
       args: entities, Model.refprop"""
    #fields = [(entity, prop) for entity in entities for prop in props]
    fields = []
    for prop in props:
        for entity in entities:
            if prop.get_value_for_datastore(entity):
                fields.append((entity, prop))
    ref_keys = [prop.get_value_for_datastore(x) for x, prop in fields]
    ref_entities = dict((x.key(), x) for x in db.get(set(ref_keys)))
    for (entity, prop), ref_key in zip(fields, ref_keys):
        prop.__set__(entity, ref_entities[ref_key])
    return entities

def prefetch_product_files(products):
    "Get all the files for the Product.files list in one get. Returns products with .files." 
    if not products:
        return None
    file_keys = []
    for product in products: file_keys.extend(product.files)
    product_files = dict((x.key(), x) for x in db.get(file_keys))
    for product in products:
        files = []
        for file_key in product.files:
            if product_files[file_key].content_type == 'pay':
                files.append(product_files[file_key])
        product.pay_files = files
    return products

def serialize_entities(models):
    """Encode/Decode to Protocol Buffers before/after pickling. 
       from http://blog.notdot.net/2009/9/Efficient-model-memcaching"""
    if models is None:
        return None
    elif isinstance(models, db.Model):# Just one instance
        return db.model_to_protobuf(models).Encode()
    else:# A list
        return [db.model_to_protobuf(x).Encode() for x in models]

def deserialize_entities(data):
    if data is None:
        return None
    elif isinstance(data, str):# Just one instance
        return db.model_from_protobuf(entity_pb.EntityProto(data))
    else:
        return [db.model_from_protobuf(entity_pb.EntityProto(x)) for x in data]

def slugify(string):
    string = string.lower()
    string = string.replace(' ', '-')
    return string

class Page(search.Searchable, db.Model):
    title = db.StringProperty()
    created_date = db.DateTimeProperty(auto_now_add=True)
    last_update = db.DateTimeProperty(auto_now=True)
    text = db.TextProperty(required=False)
    url = db.StringProperty()
    
    INDEX_ONLY = [ 'title', 'text' ]
    
    def delete(self, *args, **kwargs):
        try: memcache.delete(slugify(self.title), namespace='pages')
        except: pass
        db.Model.delete(self)
        return
    
    def put(self, *args, **kwargs):
        try: memcache.delete(slugify(self.title), namespace='pages')
        except: pass
        db.Model.put(self)
        self.index()
        return

class PageForm(djangoforms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'size':'53','maxlength':'65'}))
    text = forms.CharField(required=False, widget=forms.Textarea(attrs={'cols': 70, 'rows': 25}))
    
    class Meta:
        model = Page
        exclude = ('created_date',
                   'last_update',
                   'url')
    
    def clean(self):
        """Check the cleaned data to make sure this page doesn't already exist.
           Compare slugified url to see if the same title has been used. """
        cleaned_data = self.cleaned_data
        query = Page.all(keys_only=True)
        cleaned_title = cleaned_data.get('title')
        query.filter("url =", "%s" % slugify(cleaned_title)) #make sure this title does not matched any slugged title
        result_key = query.get()
        if result_key:
            #make sure there is a key (won't be if it's a new submission)
            try: current_key = self.instance.key()
            except: current_key = None
            #check to see if the key for this page matches the one in the datastore
            if result_key == current_key:
                return cleaned_data
            #if the key doesn't match or doesn't exist we return an error
            else:
                #these are not in self._errors now 
                msg = u"This title has already been taken"
                self._errors['title'] = ErrorList([msg])
                #this field is no longer clean, so we need to remove it
                del cleaned_data['title']  
        # always return cleaned data
        return cleaned_data    

class Product(search.Searchable, db.Model):
    title = db.StringProperty()
    active = db.BooleanProperty(default=True) #whether or not shown to non-admins
    available = db.BooleanProperty(default=True, indexed=False) #whether purchaseable
    created_date = db.DateTimeProperty(auto_now_add=True)
    description = db.StringProperty()
    #don't use referenceprop on ProductFile, because we need to prefetch these entities for the user home page
    files = db.ListProperty(db.Key)
    last_update = db.DateTimeProperty(auto_now=True)
    price = db.FloatProperty(default=settings.PURCHASE_PRICE, indexed=False)
    tags = db.ListProperty(str)
    text = db.TextProperty(required=False)
    views = db.IntegerProperty(default=0)
    
    INDEX_ONLY = [ 'title', 'text', 'tags' ]

    def delete(self, *args, **kwargs):    
        try: memcache.delete(str(self.key().id()), namespace='products')
        except: pass
        db.Model.delete(self)
        return 
        
    def get_tags_as_string(self):
        tags_as_string = Tag.get_tags_as_string(self.tags)
        return tags_as_string
    
    def is_entity_purchased(self):
        "returns true if product has been purchased"
        purchase_item = PurchaseItem.all().filter("product =", self.key()).get()
        if purchase_item:
            return True
        else: return False

    def put(self, *args, **kwargs):    
        try: memcache.delete(str(self.key().id()), namespace='products')
        except: pass
        db.Model.put(self)
        return
     
    def verify_file_list(self):
        "Check Product.files against existing ProductFiles to make sure we have the correct number. Returns file list."
        number_list_files = len(self.files)
        product_files = ProductFile.all().filter('product =', self).fetch(20)
        number_fetched_files = len(product_files)
        if number_fetched_files == number_list_files: 
            return self.files
        for file in product_files: 
            if not file.key() in self.files: 
                self.files.append(file.key())
        fetched_file_keys = []
        for file in product_files: fetched_file_keys.append(file.key())
        for file_key in self.files: 
            if not file_key in fetched_file_keys: self.files.remove(file_key)
        return self.files      
     
class ProductForm(djangoforms.ModelForm): 
    title = forms.CharField(widget=forms.TextInput(attrs={'size':'53','maxlength':'65'}))
    text = forms.CharField(widget=forms.Textarea(attrs={'cols': '70', 'rows': '25'}))
    description = forms.CharField(initial=settings.INITIAL_PRODUCT_DESCRIPTION, label=settings.PRODUCT_FORM_LABEL, required=False, widget=forms.TextInput(attrs={'size':'90','maxlength':'90'}))

    class Meta:
        model = Product
        exclude = (
                   'created_date',
                   'files',
                   'last_update',
                   'tags', 
                   'views')
        
    def clean(self):
        "check to see if the price is greater than $0.40"
        cleaned_data = self.cleaned_data
        cleaned_price = cleaned_data.get('price')
        if float(cleaned_price) > 0.4:
            return cleaned_data
        else:
            #these are not in self._errors now 
            msg = u"Product price must be greater than $0.40"
            self._errors['price'] = ErrorList([msg])
            #this field is no longer clean, so we need to remove it
            del cleaned_data['price']  
        # always return cleaned data
        return cleaned_data 

class FileData(db.Model):
    "Model to store data - only retrievable through ProductFile"
    data = db.BlobProperty()

class ProductFile(db.Model): 
    "Model to store information for files, but not the blob data"
    created_date = db.DateTimeProperty(auto_now_add=True)
    content_type = db.StringProperty(choices=('free', 'pay', 'image')) #images are used for product photos
    file = db.ReferenceProperty(FileData) 
    product = db.ReferenceProperty(Product) #to prevent orphans 
    file_type = db.StringProperty(choices=(settings.FILE_TYPES))
    
    def delete(self, *args, **kwargs):
        self.file.delete() #delete the FileData file
        db.Model.delete(self)
        return
    
class User(db.Model):
    """"Created when user logs in through Google. Key_name is Google user_id"""
    created_date = db.DateTimeProperty(auto_now_add=True)
    email = db.EmailProperty()
    purchase_access = db.BooleanProperty(default=False) #does the user have access to purchases
    storage = db.TextProperty() #for storing pickled user information
    user_id = db.StringProperty() #Google user_id
        
    def delete_sessions(self):
        sessions = Session.all().filter('user =', self.key()).fetch(10)
        for session in sessions: 
            session.delete() #delete any current or old sessions for user                   
        
class Purchase(db.Model):
    charge_date = db.DateTimeProperty()
    created_date = db.DateTimeProperty(auto_now_add=True)
    errors = db.TextProperty()  
    google_order_number = db.IntegerProperty()
    purchase_email = db.EmailProperty()
    purchase_id = db.IntegerProperty() 
    total_charge_amount = db.FloatProperty()
    user = db.ReferenceProperty(User, collection_name='purchases')
  
    def add_purchase_items(self, item_dict, user):
        """Put purchase items to datastore before charging them. User will not have access until purchase is charged.
           args: item_dict { item_id : quantity }; user instance"""
        id_list = item_dict.keys()
        products = Product.get_by_id(id_list)
        purchase_item_list = []
        for product in products:
            if product is not None:
                purchase_item = PurchaseItem(
                                             product = product,
                                             purchase = self,
                                             purchase_price = product.price,
                                             quantity = item_dict[product.key().id()],
                                             user = user,
                                             )
                purchase_item_list.append(purchase_item)
        db.put(purchase_item_list)
        return
        
    def admin_add_purchase_items(self, charge_date, product_id_list, user, total_charge_amount):
        """Put or delete multiple purchase items to datastore. Only used with /edit purchase page. 
           Args: list of product ids to be added, user instance."""
        purchase_item_list = [ x for x in self.items ]
        if product_id_list:
            product_id_current_list = []
            purchase_item_list = prefetch_refprops(purchase_item_list, PurchaseItem.product)
            for purchase_item in purchase_item_list: #create list of product ids for purchased products
                product_id_current_list.append(str(purchase_item.product.key().id()))
            product_add_id_list = [int(a) for a in product_id_list if not a in product_id_current_list]
            product_delete_id_list = [a for a in product_id_current_list if not a in product_id_list]
            item_delete_list = []
            for item_id in product_delete_id_list:
                for purchase_item in purchase_item_list:
                    if purchase_item.product.key().id() == int(item_id):
                        item_delete_list.append(purchase_item)
            if item_delete_list: db.delete(item_delete_list)    
            if product_add_id_list:
                products = Product.get_by_id(product_add_id_list)
                self.charge_date = charge_date
                self.total_charge_amount = float(total_charge_amount)
                put_list = []
                for product in products:
                    purchase_item = PurchaseItem(
                                                 expiration_date = charge_date + datetime.timedelta(days = settings.PURCHASE_DAYS),
                                                 quantity = 1, #update later
                                                 product = product,
                                                 purchase = self,
                                                 purchase_price = product.price,
                                                 user = user,
                                                 )
                    put_list.append(purchase_item)
                
                if user: #if user give user purchase access if not already
                    if not user.purchase_access: 
                        user.purchase_access = True
                        put_list.append(user)
                put_list.append(self)  
                db.put(put_list)
        else:
            db.delete(purchase_item_list)
        return
  
    def check_purchase_date(self):
        "return true if purchase is not expired"
        try:
            if datetime.datetime.now() < self.expiration_date: 
                return True
            else: return False
        except: return False      
    
    def delete(self, *args, **kwargs):
        delete_list = [ item for item in self.items ]
        delete_list.append(self)
        db.delete(delete_list)
        return
        
    def purchase_charged(self, total_charge_amount):
        "method to charge purchase which adds expiration dates to all purchase items"
        self.total_charge_amount = float(total_charge_amount)
        charge_date = datetime.datetime.now() #should convert timestamp from Google instead?
        self.charge_date = charge_date
        put_list = []
        for purchased_item in self.items:
            purchased_item.expiration_date = charge_date + datetime.timedelta(days = settings.PURCHASE_DAYS)
            put_list.append(purchased_item)
        put_list.append(self)
        db.put(put_list)
        return
        
class PurchaseForm(djangoforms.ModelForm):
    purchase_email = forms.EmailField(label="Email:", widget=forms.TextInput(attrs={'size':'53','maxlength':'65'}))
    google_order_number = forms.CharField(required=False)
    
    class Meta:
        model = Purchase
        #Only input the user email in form, so we exclude purchase_email
        exclude = ('user',
                   'purchase_id',
                   'purchase_access',
                   'created_date',
                   'errors')
      
    def clean(self):
        "check to make sure there's an email address"
        cleaned_data = self.cleaned_data
        #make sure a user exists with this email address
        email = cleaned_data.get('purchase_email')
        if not email:
            #these are not in self._errors now 
            msg = u"Please enter a valid user email address."
            self._errors['purchase_email'] = ErrorList([msg])
        return cleaned_data

class PurchaseItem(db.Model):
    expiration_date = db.DateTimeProperty() #when the purchase item expires
    product = db.ReferenceProperty() #product reference
    purchase = db.ReferenceProperty(Purchase, collection_name='items')    
    purchase_price = db.FloatProperty()
    quantity = db.IntegerProperty()
    user = db.ReferenceProperty(User, collection_name='purchase_items')
    
class RecentReminder(db.Model):
    user = db.ReferenceProperty(User, collection_name='emails')
    last_email_date = db.DateTimeProperty(auto_now=True)

class Session(db.Model, dict): #the key for each session is the uid 
    cookie = None
    expiration_date = db.DateTimeProperty()
    google_order_number = db.IntegerProperty() #only used to find session when charging purchase if no user
    __storage = db.TextProperty(indexed=False)
    user = db.ReferenceProperty(User)
    
    def add_to_cart(self, product_key, product_quantity):
        """Create 'cart' dict in session if it doesn't exist. Add cart item and quantity to 'cart' dict. 
        Raise exception if product quantity exceeds limit."""
        errors = []
        product = Product.get(product_key) #check to make sure product exists
        if not product:
            return self
        if not product.available: #make sure the product is available
            return self
        if not 'cart' in self: self['cart'] = {} #create cart if it doesn't already exist
        if not product_key in self['cart']:
            self['cart'].update({ product_key : 0 })
        self['cart'][product_key] += int(product_quantity)
        if self['cart'][product_key] > settings.MAX_QUANTITY_PER_ITEM:
            self['cart'][product_key] = settings.MAX_QUANTITY_PER_ITEM #set quantity at max
            errors.append('quantity') 
        if errors: 
            errors = build_string_from_list(errors, '-')
            raise Exception(errors)
        self['number_cart_items'] = self.calculate_number_cart_items() #update the number of cart items
        self.put() #put session
        return
    
    def add_purchase(self, purchase):
        """Add user purchases to the purchase dict in the session.
           Put session, because this is a POST method."""
        if not 'purchases' in self: self['purchases'] = []
        #if admin adds purchase items to a purchase, we need to run add_purchased_items method again
        if purchase.key() in self['purchases']: pass #return
        else:
            self['purchases'].append(purchase.key())
        self.add_purchased_items(purchase)
        self.put()
        return
    
    def add_purchased_items(self, purchase):
        """Using a purchase instance populate the purchased_products dict in the session.
           Return:
             self['purchased_products'] = { product.key : expiration date }"""
        purchase_dict = {}
        purchase_items = [ x for x in purchase.items ]
        prefetch_refprops(purchase_items, PurchaseItem.product)
        for purchase_item in purchase_items:
            purchase_dict.update({ purchase_item.product.key() : purchase_item.expiration_date  })
        if purchase_dict:
            if not 'purchased_products' in self: self['purchased_products'] = {}
            self['purchased_products'].update(purchase_dict)
        return self

    def _add_user_purchased_items(self, user):
        """Using a user instance populate the purchased_products dict in the session.
           Return:
             self['purchased_products'] = { product.key : expiration date }"""
        today = datetime.datetime.now()
        purchase_dict = {}
        if not user.purchase_access: return self #no purchases associated with this user 
        #how many days back we go for expired purchases
        expired_purchase_history = today - datetime.timedelta(days=settings.NUMBER_DAYS_EXPIRED_PURCHASES)
        purchase_items = user.purchase_items.filter('expiration_date >', expired_purchase_history).fetch(settings.SAFE_FETCH_NUMBER)
        prefetch_refprops(purchase_items, PurchaseItem.product)
        for purchase_item in purchase_items:
            purchase_dict.update({ purchase_item.product.key() : purchase_item.expiration_date  })
        if not purchase_dict: #all purchased items have expired
            user.purchase_access = False 
            user.put()
        if purchase_dict:
            if not 'purchased_products' in self: self['purchased_products'] = {}
            self['purchased_products'].update(purchase_dict)
        return self

    def calculate_total(self, cart_products=None):
        "Calculate the total of the products in the cart. Use items as kwarg in case cart_items are queried for separately."
        total_price = 0
        if not cart_products:
            if not 'cart' in self: cart_products = None
            else: cart_products = Product.get(self['cart'].keys())
        if cart_products: 
            for product in cart_products: total_price += product.price
        return total_price

    def calculate_number_cart_items(self):
        "Calculate the total of number of cart items."
        if not 'cart' in self: return 0
        if not self['cart']: return 0
        number_cart_items = sum(self['cart'].values()) #sum the values in the cart dict
        return number_cart_items

    def check_date(self):     
        "Check to make sure this session isn't expired."
        t = datetime.datetime.now()
        if t > self.expiration_date: 
            self.delete()
            return None
        return self
    
    def check_for_google_login(self, user_google):
        "Check to see if user has logged in through Google and update cart if necessary"
        #user has logged out, so session needs to be deleted
        if self.has_user() and not user_google:
            self.delete()
            self = Session.create_session(user_google)
        #user has logged in, so old session needs to be deleted
        #if there is a cart from the first session should be transferred    
        if not self.has_user() and user_google:
            if 'cart' in self: 
                cart_dict = self['cart'] #save cart from current session
            else: cart_dict = None
            #transfer any purchased products to this new session
            if 'purchased_products' in self: purchased_products = self['purchased_products']
            else: purchased_products = None
            self.delete()
            self = Session.create_session(user_google) #create new user session
            self.transfer_cart_items(cart_dict) #pass old cart values into user cart
            self['number_cart_items'] = self.calculate_number_cart_items()
            if not 'purchased_products' in self: self['purchased_products'] = {}
            self._merge_purchased_products(purchased_products)
            self['updated'] = True
        return self

    @staticmethod
    def create_session(user_google):
        """Create new session if Google login is used or if trying to access a user page. Remove
           any old sessions if this is a Google user."""
        #create a unique id and expiration date for this session
        uid = generate_session_key()
        expiration_date = datetime.datetime.now() + datetime.timedelta(days=settings.SESSION_LENGTH)
        if user_google:
            user_id = user_google.user_id()
            #check to see if this user is currently in the datastore
            user = User.get_by_key_name(user_id)
            if user: user.delete_sessions() #delete old user sessions
            #create new user if one doesn't already exist
            if not user: #generate different key for user
                user = User(key_name = user_id, user_id = user_id, email = user_google.email())
                user.put()
            session = Session(key_name = uid, expiration_date = expiration_date, user = user)
            session._add_user_purchased_items(user) # SHOULD ONLY DO THIS FOR NON ADMIN USERS
        else: 
            session = Session(key_name = uid, expiration_date = expiration_date)
        session.cookie = SessionCookie.set_cookie('uid', uid, settings.SESSION_LENGTH)  
        session['updated'] = True
        session['number_cart_items'] = session.calculate_number_cart_items()
        return session

    def delete(self, *args, **kwargs):
        try: memcache.delete(str(self.key().name()), namespace='sessions') 
        except: pass
        db.Model.delete(self)
        return

    def get_cart_products(self):
        "Return a list of products from the session cart list"
        if not 'cart' in self: return None
        cart_products = []
        products = Product.get(self['cart'].keys())
        for product in products:
            product.quantity = self['cart'][str(product.key())]
            cart_products.append(product)
        return cart_products
                
    def get_purchased_products(self):
        "Get the purchases in purchased_products dict and test to make sure that product is not expired"
        if not 'purchased_products' in self: return None
        try: 
            purchased_products = memcache.get(str(self.session.key().name()), namespace='purchases')
            return purchased_products
        except: pass
        today = datetime.datetime.now()
        purchased_products = []
        products = Product.get(self['purchased_products'].keys())
        for product in products:
            product.expiration_date = self['purchased_products'][product.key()]
            if product.expiration_date < today: product.expiration_date = False #don't allow access if expired
            purchased_products.append(product)
        if purchased_products:
            purchased_products = prefetch_product_files(purchased_products)
            #only add to memcache for 30 minutes in case a purchase expires
            try: memcache.add(str(self.session.key().name()), purchased_products, 900, namespace='purchases')
            except: pass
            return purchased_products
        return None

    @staticmethod
    def get_session(uid):
        "Get and return session from cookie. Return None if no session."
        session = None
        if uid: 
            session = memcache.get(uid, namespace='sessions')
            if session is None:
                session = Session.get_by_key_name(uid)
                if session is None: return None
                else: 
                    session.load_values() #only load values from datastore
                    try: memcache.add(uid, session, settings.MEMCACHE_SESSION_LENGTH, namespace='sessions')
                    except: pass 
            session = session.check_date()
            session['updated'] = False
            return session
        else: return None

    def has_user(self):
        key = Session.user.get_value_for_datastore(self)
        if key: return True
        else: return False

    def is_product_purchased(self, product_key):
        "returns the expiration date if the item has been purchased recently; returns False if not"
        today = datetime.datetime.now()
        if not 'purchased_products' in self: return False
        if product_key in self['purchased_products']: 
            if self['purchased_products'][product_key] > today: 
                return self['purchased_products'][product_key]
        return False

    def load_values(self):
        try:
            storage_dict = pickle.loads(str(self.__storage))
            self.update(storage_dict)
        except: pass
        return self
    
    def _merge_cart(self, product_keys, item_quantities):
        """Used to merge user cart with session cart.
        Args:
            product_keys: list of product keys from session cart
            item_quantities: list of item quantities from session cart
        """
        if not 'cart' in self: self['cart'] = {}
        for product_key, item_quantity in zip(product_keys, item_quantities):
            item_quantity = int(item_quantity)
            if product_key in self['cart']:
                self['cart'][product_key] += item_quantity
                if settings.MAX_QUANTITY_PER_ITEM < self['cart'][product_key]:
                    self['cart'][product_key] = settings.MAX_QUANTITY_PER_ITEM
            else: #product does not already exist in cart
                self['cart'][product_key] = item_quantity
        return self

    def _merge_purchased_products(self, purchased_products):
        "Merge purchased_products from old session with new session. Make sure expiration date is more recent." 
        if not purchased_products: return self
        for key, date in purchased_products.items():
            if key in self['purchased_products']: #see if this purchase is already in self
                if date > self['purchased_products'][key]: #update only if expiration date is greater
                    self['purchased_products'].update({ key : date })
            else: self['purchased_products'].update({ key : date })
        return self

    def put(self, *args, **kwargs):
        "Pickle the session dict and copy it to the user if there is a user."
        self.cookie = None #remove cookie
        if 'updated' in self: del self['updated'] #remove the update flag
        self.__storage = pickle.dumps(self.items())
        put_list = []
        if self.has_user(): 
            self.user.storage = self.__storage
            put_list.append(self.user) #put user if there is one to save changes to user cart
        put_list.append(self)
        db.put(put_list)
        try: memcache.set(str(self.key().name()), self, settings.MEMCACHE_SESSION_LENGTH, namespace='sessions')
        except: pass
        
    def remove_from_cart(self, product_key):
        """Remove one item from the cart. Put session, because this is a POST method"""
        if not 'cart' in self: return
        if product_key in self['cart']: del self['cart'][product_key]
        self['number_cart_items'] = self.calculate_number_cart_items()
        self.put()
        return self
        
    def transfer_cart_items(self, cart_dict):
        """Retrieve the saved cart for the user in user.storage. Update current session with saved user cart.
           Add in cart items for the old deleted session.
           Args: cart_dict from the old session""" 
        self['cart'] = {}
        try:    
            user_storage = pickle.loads(str(self.user.storage))#get the user cart
            self.update(user_storage)
        except: pass
        if cart_dict:
            self._merge_cart(cart_dict.keys(), cart_dict.values()) 
        return self
        
    def update_cart(self, product_keys, item_quantities):
        """Update the cart with the item key and quantity.  
        Raises error if quantity exceeds max amount. 
        Put session, because this is a POST method.
        Args:
            product_keys: list of product keys
            item_quantities: list of item quantities
        """
        errors = []
        if not 'cart' in self: self['cart'] = {}
        for product_key, item_quantity in zip(product_keys, item_quantities):
            item_quantity = int(item_quantity)
            if product_key in self['cart']: #make sure the product key is in the cart
                if item_quantity == 0: #remove product if quantity falls to 0
                    del self['cart'][product_key]
                elif self['cart'][product_key] != item_quantity: #only adjust if quantity changes
                    if settings.MAX_QUANTITY_PER_ITEM < item_quantity:
                        item_quantity = settings.MAX_QUANTITY_PER_ITEM
                        if not errors: #this is the only error, so only raise if no errors already
                            errors.append('quantity')
                    self['cart'][product_key] = item_quantity                
        self.put()
        if errors:
            errors = build_string_from_list(errors, '-')
            raise Exception(errors)
        return   

class SessionCookie():
    @staticmethod  
    def set_cookie(cookie_type, cookie_value, days_until_expiration):
        "to create, adjust, and delete cookies"
        expiration = datetime.datetime.now() + datetime.timedelta(days=days_until_expiration)
        cookie = Cookie.SimpleCookie()
        cookie[cookie_type] = str(cookie_value)
        cookie[cookie_type]["path"] = "/"
        cookie[cookie_type]["expires"] = expiration.strftime("%a, %d-%b-%Y %H:%M:%S PST")
        return cookie

class Tag(db.Model):
    title = db.StringProperty()
    tagged = db.ListProperty(db.Key) #items that have been tagged

    @staticmethod
    def clean_tags(tag_string, string_separator):
        "separates tag string to create a list of tags with a maximum of 5 tags returned"
        tag_string = str(tag_string)
        tag_list = tag_string.split(string_separator)
        tag_list = tag_list[0:4] #limit tags to 5 only
        revised_tag_list = []
        for tag in tag_list:
            tag = tag.strip() #remove whitespace
            if len(tag) > 0: revised_tag_list.append(tag) #remove empty spaces
        revised_tag_list = set(revised_tag_list) #remove duplicates
        final_tag_list = []
        for a in revised_tag_list:
            final_tag_list.append(a)
        final_tag_list.sort()
        return final_tag_list

    @staticmethod
    def expire_memcache_tags():
        try: memcache.delete('tag_dict')
        except: pass
        return
        
    @staticmethod
    def get_tag_dict():
        "return a dict of all the tag names"
        tag_dict = memcache.get('tag_dict')
        if not tag_dict:
            tags = Tag.all().order('title').fetch(1000)
            tag_dict = {}
            for tag in tags: tag_dict.update({ tag.title : tag.title.replace('_', ' ')}) 
            memcache.add('tag_dict', tag_dict)
        return tag_dict
    
    @staticmethod
    def get_tags_as_string(tag_list):
        tags_as_string = ''
        for tag in tag_list:
            if len(tags_as_string) != 0:
                tags_as_string += ', ' 
            tags_as_string += tag
        return tags_as_string
    
    @staticmethod
    def update_tags(new_tag_list, old_tag_list, product):
        "compare new tags to old tags; add/delete product from tags; add new tags; remove unused tags"
        added_tags = [a for a in new_tag_list if not a in old_tag_list]
        deleted_tags = [a for a in old_tag_list if not a in new_tag_list]
        tag_put_list = []
        tag_delete_list = []
        if added_tags or deleted_tags:
            if added_tags:
                tag_key_list = []
                for tag_name in added_tags: #add or update datastore tag 
                    tag_key_list.append('tag_' + tag_name)
                tags = Tag.get_by_key_name(tag_key_list)
                tag_dict = dict(zip(tag_key_list, tags))
                for tag_name in added_tags: 
                    if tag_dict['tag_' + tag_name] is None: #new tag
                        tag = Tag(key_name = 'tag_' + tag_name, tagged = [product.key()], title = tag_name)
                        tag_put_list.append(tag)
                    else: #update existing tag with new product
                        tag = tag_dict['tag_' + tag_name]
                        if not product.key() in tag.tagged: #make sure the key is not already there 
                            tag.tagged.append(product.key())
                            tag_put_list.append(tag)
            if deleted_tags:
                for tag_name in deleted_tags: #delete or update datastore tag
                    tag = Tag.get_by_key_name('tag_' + tag_name)
                    if tag:
                        if product.key() in tag.tagged: tag.tagged.remove(product.key()) #delete product from tag
                        if not tag.tagged: tag_delete_list.append(tag) #remove tag if tagged list is empty
                        else: tag_put_list.append(tag)
        if tag_put_list: db.put(tag_put_list)
        if tag_delete_list: db.delete(tag_delete_list)
        if tag_put_list or tag_delete_list: Tag.expire_memcache_tags()
        return
            
class Pagination():
    model_dict = { 'pages' : Page, 'products' : Product, 'purchases' : Purchase, 'users' : User, 'sessions' : Session }
    
    def get_bookmark_key(self, model_name, data):
        "for getting the back bookmark key"
        if model_name == 'users' or model_name == 'sessions': back_bookmark = data.key()
        else: back_bookmark = data.key().id()
        return back_bookmark
    
    def get_bookmark(self, model_name, bookmark_key):
        if model_name == 'users' or model_name == 'sessions':
            bookmark = self.model_dict[model_name]().get(bookmark_key)
        else:
            bookmark_key = int(bookmark_key)
            bookmark = self.model_dict[model_name]().get_by_id(bookmark_key)
        return bookmark
    
    def get_values(self, request, model_name, data_query, is_admin = False):
        """returns a template dict with next and back url values and entity data
                args:   request - the request object from webapp
                        model_name - name of the model Class
                        query - a query with filters applied  
        """
        attribute_sort_dict = {  #dict with list of attributes that can be used to sort, first tribute is the default
                              'pages' : [ 'title' ], 
                              'products' : [ 'title', 'views' ],
                              'purchases' : [ 'created_date' ],
                              'sessions' : [ 'expiration_date' ], 
                              'users' : [ 'created_date' ],
                              }
        user_attribute_sort_dict = {  #users may only use these sorts 
                                  'pages' : [ 'title', 'title_reverse' ], 
                                  'products' : [ 'title', 'title_reverse', 'views_reverse' ],
                                  }
        if not data_query: data_query = self.model_dict[model_name].all()
        sort = request.get('sort')
        if sort and not is_admin: #check to make sure the ONLY certain filters are used
            if not sort in user_attribute_sort_dict[model_name]:
                return False
        if not sort: #default sorting
            order_attribute = attribute_sort_dict[model_name][0]
            if model_name == 'users' or model_name == 'sessions' or model_name == 'purchases' : reverse_order = True
            else: reverse_order = False
        else: #sort is formated like so - 'title_reverse' - for reverse title sort
            split_sort = sort.split('_')
            if len(split_sort) > 1: #reverse order 
                reverse_order = True
            else: 
                reverse_order = False
            order_attribute = split_sort[0]
            if not split_sort[0] in attribute_sort_dict[model_name]: return False
        back = request.get('back')    
        bookmark_key = request.get('bookmark')
        next_bookmark = None
        back_bookmark = None
        #for sorting and reverse sorting
        if reverse_order == True:
            query_order = '-' + order_attribute
            query_reverse_order = order_attribute
        else: 
            query_order = order_attribute
            query_reverse_order = '-' + order_attribute
        try:   
            if back and bookmark_key:                 
                next_bookmark = bookmark_key
                bookmark = self.get_bookmark(model_name, bookmark_key)
                #get the attribute from the bookmark that we will order by
                bookmark_attribute = getattr(bookmark, order_attribute)
                if reverse_order == True: filter_inequality = ' >'
                else: filter_inequality = ' <'
                data_query.order(query_reverse_order).filter((order_attribute + filter_inequality), bookmark_attribute)
                data = data_query.fetch(settings.PAGE_SIZE+1)
                #check to see if we need a back button
                if len(data) == settings.PAGE_SIZE+1:
                    back_bookmark = self.get_bookmark_key(model_name, data[settings.PAGE_SIZE-1])
                    data = data[:settings.PAGE_SIZE]
                data.reverse()
            elif bookmark_key: #if there is a bookmark and no 'back' then we must be next
                bookmark = self.get_bookmark(model_name, bookmark_key)
                bookmark_attribute = getattr(bookmark, order_attribute)
                if reverse_order == True: filter_inequality = ' <='
                else: filter_inequality = ' >='    
                data_query.order(query_order).filter((order_attribute + filter_inequality), bookmark_attribute)
                data = data_query.fetch(settings.PAGE_SIZE+1)
                back_bookmark = self.get_bookmark_key(model_name, data[0])
            else: 
                data_query.order(query_order)
                data = data_query.fetch(settings.PAGE_SIZE+1)
            if len(data) == settings.PAGE_SIZE+1:
                next_bookmark = self.get_bookmark_key(model_name, data[-1])
                data = data[:settings.PAGE_SIZE]
            if next_bookmark: next_url = build_url({ 'item' : model_name, 'bookmark' : next_bookmark, 'sort' : sort})
            else: next_url = None
            if back_bookmark: back_url = build_url({ 'item' : model_name, 'bookmark' : back_bookmark, 'back' : 'true', 'sort' : sort})
            else: back_url = None
        except: 
            return False
        template_values = { model_name : data, 'next_url' : next_url, 'back_url' : back_url }
        return template_values

class UserForm(djangoforms.ModelForm): #not sure why but this model needs to be at the end of the page
    email = forms.EmailField(widget=forms.TextInput(attrs={'size':'53','maxlength':'65'}))
        
    class Meta:
        model = User
        exclude = (
                   'cart',
                   'created_date',
                   'purchase_access',
                   'storage',
                   'user_id')
    
    def clean(self):
        "check to see if this user email address exists and make sure an email is added"
        cleaned_data = self.cleaned_data
        cleaned_attribute = cleaned_data.get('email')
        query = User.all(keys_only=True).filter("email =", "%s" % cleaned_attribute)
        result_key = query.get()
        if result_key:
            #make sure there is a key (won't be if it's a new submission)
            try: current_key = self.instance.key()
            except: current_key = None
            #check to see if the key for this page matches the one in the datastore
            if result_key == current_key: return cleaned_data
            #if the key doesn't match or doesn't exist we return an error
            else:
                msg = u"This email has already been taken"
                self._errors['email'] = ErrorList([msg])
                #this field is no longer clean, so we need to remove it
                del cleaned_data['email']
        if not cleaned_attribute:
            msg = u"Please enter an email address."
            self._errors['email'] = ErrorList([msg])
        return cleaned_data

