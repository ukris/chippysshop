from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext import webapp
import datetime
import models
import settings

class DatabaseMaintenance(webapp.RequestHandler):
    def get(self, page_name):
        current_time = datetime.datetime.now()
        if page_name == 'daily':
            self.update_product_views()
        elif page_name == 'daily2':
            self.delete_sessions(current_time)
            self.delete_recent_emails(current_time)
            return
        elif page_name == 'daily3':
            self.delete_purchase_items(current_time)
        else: return    
    
    def delete_purchase_items(self, current_time):
        "delete all purchases and purchase items older than 2 years."
        purchase_list = []
        t = current_time - datetime.timedelta(days = 730)
        old_purchase_items = models.PurchaseItem.all().filter("expiration_date <", t).fetch(settings.SAFE_FETCH_NUMBER)
        for item in old_purchase_items:
            key = models.PurchaseItem.purchase.get_value_for_datastore(item)
            purchase_list.append(key)
        purchase_list = set(purchase_list)
        old_purchases = db.get(purchase_list)
        db.delete(old_purchases)
        db.delete(old_purchase_items)
        return    
    
    def delete_recent_emails(self, current_time):
        "delete recent emails older than 2 days"     
        t = current_time - datetime.timedelta(days = 2)
        old_emails = models.RecentReminder.all(keys_only=True).filter("last_email_date <", t).fetch(settings.SAFE_FETCH_NUMBER)
        db.delete(old_emails)
        return
    
    def delete_sessions(self, current_time):
        "delete all sessions older than days specified in settings"      
        t = current_time
        delete_list = []
        old_sessions = models.Session.all().filter("expiration_date <", t).fetch(settings.SAFE_FETCH_NUMBER)
        delete_list.extend(old_sessions)
        old_session_keys = [ str(x.key().name()) for x in old_sessions ]
        memcache.delete_multi(old_session_keys, namespace='sessions')
        return
    
    def update_product_views(self):
        "Retrieve product views counters, increase product.views, and put back to datastore."
        products = models.Product.all().fetch(settings.SAFE_FETCH_NUMBER)
        product_id_list = []
        for product in products:
            product_id_list.append(str(product.key().id()))
        #not sure if there's a way to get all entities in a namespace, so we don't look for all products    
        try: product_counters = memcache.get_multi(product_id_list, namespace='counters')
        except: products = None
        if products:
            for product in products: 
                try: 
                    product.views += int(product_counters[str(product.key().id())])
                except: pass
            db.put(products)
        return
    