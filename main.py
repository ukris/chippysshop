"""
Chippy's Shop

Copyright (C) 2010 Jason LaPoint <jasonlapoint@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
for k in [k for k in sys.modules if k.startswith('django')]: 
    del sys.modules[k]
from google.appengine.dist import use_library
use_library('django', '1.0')
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import googlecheckout
import maintenance
import settings
import testhandler
import views

application = webapp.WSGIApplication([
                                      ('/test/(.*)', testhandler.TestHandler), #delete this
                                      ('/products/(.*)/(.*)', views.ProductHandler),
                                      ('/tags/(.*)', views.TagHandler),
                                      ('/upload/(.*)/(.*)', views.UploadHandler),
                                      ('/files/free/(.*)/.*', views.FreeFileHandler),
                                      ('/files/image/(.*)/.*', views.FreeFileHandler),
                                      ('/files/pay/(.*)/.*', views.PaidFileHandler),
                                      ('/admin/(.*)', views.AdminHandler),
                                      ('/edit', views.EditHandler),
                                      ('/search', views.SearchHandler),
                                      ('/google_checkout/.*', googlecheckout.GoogleListener), #add merchant key to directory!
                                      ('/user/(.*)', views.UserHandler), 
                                      ('/maintenance/(.*)', maintenance.DatabaseMaintenance),  
                                      ('/(.*)', views.PageHandler),
                                      ],
                                     debug=settings.ENABLE_DEBUG)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()