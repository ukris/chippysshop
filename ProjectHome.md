### Chippy's Shop ###
Chippy's Shop (CS) uses Google's App Engine and Django 1.0 to create a website for selling subscriptions to files online. It posts user shopping carts to Google Checkout and creates a purchase entity in the datastore when a purchase is completed. Users have the option of signing in through Google's account system or can simply use the purchase code that is emailed to them to gain access to
their purchases.

CS uses Bill Katz's Search (http://www.billkatz.com/2009/6/Simple-Full-Text-Search-or-App-Engine), Blueprint CSS (http://www.blueprintcss.org/), YUI's AutoComplete and Rich Text Editor (http://developer.yahoo.com/yui/), and a shopping cart image created by Eoin McGrath ("http://www.starfishwebconsulting.co.uk").

This is my first Python project, so the code can use a cleanup. I'm planning on adding more features like Amazon FPS integration and support for selling physical items.

Contact me at jasonlapoint@gmail.com if you're interested in contributing to this project.

### Settings.py ###
Settings.example.py needs to be changed to settings.py, app.yaml needs to be updated with you application name and version, and the logo image needs to be changed.

### Your First Page ###
You will need login as an App Engine admin user to create a page titled "home" for the homepage. Otherwise users will get an error message when accessing your default page.

### Admin Page ###
From here you can add pages, products, users, purchases, etc. It's not pretty, but it works.

### Sessions ###
CS includes a simple cookie-based session system. No personal information is stored in the cookies. No personal information is accessible by a logged user. Even if a session is compromised, no personal information can be viewed or changed. At worst a compromised session gives access to a user's purchased files. Only the Admin users that login through their Google Account have access to user email accounts. For now sessions are only created when a user accesses the cart or "My Purchased Products" page.

### Google Checkout ###
CS supports Level 2 integration with Google Checkout and uses the XML notification API. After making a purchase, users are emailed their access code, so that they may download their purchased files from the website.

You will need to make the following changes to your Google Checkout Merchant Account in order to use the purchase functionality:
  1. Under Settings ---> Integration. Input your API callback url, which should look like: https://yourwebsite.appspot.com/google_checkout/
  1. Under Settings ---> Integration. Under Advanced settings check the box for "Require notification acknowledgments to specify the serial number of the notification."
  1. Under Settings ---> Integration. Choose API version 2.0 (not tested under other versions).
  1. Under Settings ---> Preferences. Choose to automatically authorize and charge the buyer's credit card.

### Sample Site ###
Check out the test site at http://mychippyshop.appspot.com.

### Current Priorities ###
  * Bug fixes
  * Amazon FPS integration
  * Support for selling physical items
  * Product review system
  * Javascript viewer for multiple images

### Contact ###
For questions or to contribute to the project, you can contact me at jasonlapoint@gmail.com.