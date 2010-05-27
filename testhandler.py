import pickle

from google.appengine.dist import use_library
use_library('django', '1.0')
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext import db

import emails
import googlecheckout
import models
import settings

class TestHandler(webapp.RequestHandler):
    def get(self, page_name):
        if users.is_current_user_admin():
            if page_name == 'delete':
                #query = models.Purchase.all().fetch(100)
                #for purchase in query:
                #    purchase.delete()
                query = models.Session.all().fetch(100)
                for session in query:
                    session.delete()
                try: 
                    memcache.flush_all()
                    print 'memcache flushed'
                except: print 'Unable to clear memcache'
                print 'success'
            elif page_name == 'test':
                print 'sessions'
                sessions = models.Session.all().fetch(100)
                for session in sessions: 
                    print '\nsession key name: %s' % str(session.key().name())
                    print '\nhas user: %s' % session.has_user()
                    session = session.load_values()
                    print '\nsession dict: %s' % session.items()
                    print '\nsession.google_order_number: %s' % session.google_order_number
                print '\ntest'
                all_users = models.User.all().fetch(100)
                for user in all_users:
                    print '\nuser key: %s' % str(user.key())
                    print '\nuser email: %s' % str(user.email)
                    if user.storage:
                        print '\nuser cart: %s' % (pickle.loads(str(user.storage)))
                purchase_items = models.PurchaseItem.all().fetch(100)
                for item in purchase_items: 
                    print '\nproduct title: %s' % item.product.title
                    print '\npurchase.user.key(): %s' % item.user.key()
                    print '\npurchase.expiration_date: %s' % item.expiration_date
                    print '\npurchase.quantity: %s' % item.quantity
                purchases = models.Purchase.all().fetch(100)
                for purchase in purchases: 
                    print '\npurchase charge date: %s' % str(purchase.charge_date)
                    purchase.purchase_charged(3)
                    print purchase.charge_date
            elif page_name == 'test2':
                purchase_items = models.PurchaseItem.all().fetch(100)
                print 'test'
                for item in purchase_items: 
                    print '----------------------------------------------------------------------------------------------------------'
                    print '\nproduct title: %s' % item.product.title
                    print '\npurchase.user.key(): %s' % item.user.key()
                    print '\npurchase.expiration_date: %s' % item.expiration_date
                    print '\npurchase.quantity: %s' % item.quantity  
 
            elif page_name == 'products':
                products = models.Product.all().fetch(100)
                print 'test'
                for product in products:
                    print 'product id: %s' % product.key().id()
                    print 'product title: %s' % product.title
            elif page_name == 'new_order':
                #for testing purchases
                notification = googlecheckout.parse_google_response(settings.TEST_NEW_ORDER_NOTIFICATION)
                #notification = self.parse_google_response(settings.ORDER_TEST)
                #print 'test'
                googlecheckout.manipulate_notification(notification)
            elif page_name == 'charge':
                #for testing purchases
                notification = googlecheckout.parse_google_response(settings.ORDER_2)
                googlecheckout.manipulate_notification(notification)
            else:
                self.redirect('/')
            return
        
