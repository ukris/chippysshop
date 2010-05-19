from google.appengine.api import mail
import datetime

import settings
import models

def mail_user_purchase(email, purchase_key):
    "Mail user the purchase key"
    body = """Your purchased forms are now available at %s. To access your forms visit %s/user/home?key=%s.  
      
If you did not login using your Google Account, you will need to enter the following user key: %s.
      
Please email %s if you have any questions.
      
                  Regards,
                  
                  The %s Team""" % (settings.SITE_NAME, settings.SITE_URL, purchase_key, purchase_key, settings.SITE_EMAIL, settings.SITE_NAME)
    body = body + settings.EMAIL_CLOSING
    subject = 'Access to ' + settings.SITE_NAME
    mail_user(email, body, subject)
    return

def mail_user_reminder(email, purchase_keys, user):
    """Mail user reminder once per 24 hour period returns an error if an email has been sent recently.
       Args:
           email: email string
           purchase_keys: list of string keys
           user: user instance"""
    purchase_keys = models.build_string_from_list(purchase_keys, ', ')       
    has_recent_email = has_recent_email(user)
    if has_recent_email: 
        return True
    body = """Your purchased forms are available at %s. To access your forms visit %s/user/home. 
      
Enter the following key to access your purchases: %s.
      
Please email %s if you have any questions.
           
                  Regards,
                  
                  The %s Team""" % (settings.SITE_NAME, settings.SITE_URL, purchase_keys, settings.SITE_EMAIL, settings.SITE_NAME)
    body = body + settings.EMAIL_CLOSING
    subject = 'Access to ' + settings.SITE_NAME
    mail_user(email, body, subject)
    recent_reminder = models.RecentReminder(user=user)
    recent_reminder.put()
    return False
        
def mail_user(email, body, subject):
    sender = settings.SITE_NAME + ' <' + settings.SITE_EMAIL + '>'
    recipient = '<' + str(email) + '>'
    mail.send_mail(sender = sender,
                   to = recipient,
                   subject = subject,
                   body = body)
    
def mail_admin(body, subject):
    email = settings.SITE_EMAIL
    mail_user(email, body, subject)
       
def has_recent_email(user):
    "method to ensure user is only emailed once per 24 hour period"
    now = datetime.datetime.now()
    t = now - datetime.timedelta(days = 1)
    recent_email = user.emails.order('last_email_date').get() #models.RecentReminder.all().order('last_email_date').filter('user =', user).get()
    if recent_email and recent_email.last_email_date > t: return True
    else: return False
