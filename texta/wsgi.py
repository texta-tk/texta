### THIS IS FOR SETTING UP TEXTA WITH WSGI/APACHE2

import os
import sys
from django.core.wsgi import get_wsgi_application

# change these 
sys.path.append("/var/www/texta/")
sys.path.append("/usr/lib/python2.7/dist-packages/")
sys.path.append("/")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texta.settings")

application = get_wsgi_application()
