ENABLE_DEBUG = True
ENABLE_STATS = True #unable to disable?
FILE_TYPES = ['pdf', 'doc', 'rtf', 'gif', 'jpg', 'png']
MAX_QUANTITY_PER_ITEM = 1
MEMCACHE_LENGTH = 3600 #default memcache length in seconds
MEMCACHE_SESSION_LENGTH = 3600 #number of seconds to store memcache data
NUMBER_POPULAR_PRODUCTS = 6
NUMBER_DAYS_EXPIRED_PURCHASES = 120 #how many days back for displaying old purchases
PAGE_SIZE = 10 #number of items displayed per page
PAY_FILE_TYPES = 'Adobe PDF' #set to False to display extension of pay files that exist for product
PURCHASE_DAYS = 60 #how long for purchase access
PURCHASE_PRICE = 3.00 #default purchase price
PURCHASE_ID_START = 999 #purchase id start number
SAFE_FETCH_NUMBER = 300 #number of entities to fetch during large tasks
SESSION_LENGTH = 5 #session length in days
SITE_DOWN_MESSAGE = "The website is currently undergoing maintenance  and will be back online shortly."
SITE_EMAIL = 'myemail@email.com'
SITE_NAME = "Chippy's Shop"
SITE_URL = 'http://www.mychippyshop.com'
TAG_NAME = 'Category'

INITIAL_PRODUCT_DESCRIPTION = str(PURCHASE_DAYS) + ' days of access to the PDF version of the document.'
PRODUCT_FORM_LABEL = 'Short description for Google Checkout (leave blank for default description)'

#Error messages
ERROR_EMAIL = 'There are no purchases with that email address.'
ERROR_EMAIL_LIMIT = 'Only one reminder email can be sent every 24 hours.'
ERROR_GOOGLE_POST = 'An error occurred during checkout. Please try again.'
ERROR_PRODUCT_PURCHASED = "This product has been purchased, so it can't be deleted."
ERROR_QUANTITY = 'You may only add ' + str(MAX_QUANTITY_PER_ITEM) + ' of each item.'
ERROR_KEY = 'Incorrect key. Make sure there are no spaces before or after your key.' 
ERROR_DICT = { 'email': ERROR_EMAIL, 'email_limit': ERROR_EMAIL_LIMIT, 'key': ERROR_KEY, 'google_post' : ERROR_GOOGLE_POST, 'quantity' : ERROR_QUANTITY, 'product_purchased' : ERROR_PRODUCT_PURCHASED }

#Notice messages
NOTICE_EMAIL = 'Your purchase key has been emailed.'
NOTICE_ITEM_USED = 'Unable to delete, because this product has been purchased.'
NOTICE_PURCHASE_ADDED = 'Purchase added.'
NOTICE_DICT = { 'email': NOTICE_EMAIL, 'item_used' : NOTICE_ITEM_USED, 'purchase': NOTICE_PURCHASE_ADDED }

#Google Checkout
#MERCHANT_ID = '' 
#MERCHANT_KEY = ''
MERCHANT_KEY = '' #sandbox
MERCHANT_ID = '' #sandbox
GOOGLE_ANALYTICS_ACCOUNT = ''

#GOOGLE_URL = 'https://checkout.google.com/api/checkout/v2/merchantCheckout/Merchant/' + MERCHANT_ID
GOOGLE_URL = 'https://sandbox.google.com/checkout/api/checkout/v2/merchantCheckout/Merchant/' + MERCHANT_ID #sandbox

#Google checkout text after successful transaction
DOWNLOAD_INSTRUCTIONS = 'Your access key to the website has been emailed to you. Please check your email and return to ' + SITE_URL + '/user/home to access your purchase.'

NEW_ORDER_NOTIFICATION = [
                          'session-key-name',
                          'google-order-number',
                          'merchant-item-id',
                          'quantity',
                          ]

RISK_INFORMATION_NOTIFICATION = [
                                 'google-order-number',
                                 ]
ORDER_STATE_CHANGE_NOTIFICATION = [
                                   'google-order-number',
                                   ]
AMOUNT_NOTIFICATION = [
                       'google-order-number',
                       'total-charge-amount',
                       ]



