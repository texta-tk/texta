import django # For making sure the correct Python environment is used.
from texta.settings import INSTALLED_APPS, DATABASES
import subprocess
from time import sleep
import shutil
import sys
import os
import time
import datetime
import shutil
import glob
import re
import operator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texta.settings")
django.setup()
from django.contrib.auth.models import User

BACKUP_STRFTIME_FORMAT = '%Y-%m-%d %H-%M-%S'
BACKUP_DATE_PATTERN = re.compile('pre-(\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})')


def create_admin():
    u = User(username='admin')
    u.set_password('1234')
    u.is_superuser = True
    u.is_staff = True
    
    try:
        u.save()
        return True
    except:
        return False


cwd = os.path.realpath(os.path.dirname(__file__))

custom_apps = [app for app in INSTALLED_APPS if not app.startswith('django')] # Migration works for custom apps only. Manage.py can't detect relevant built-in django apps.


if len(sys.argv) > 1:
    if sys.argv[1] == 'purge_migrations':
        print('Deleting migrations...')
        for custom_app in custom_apps:
            migrations_dir = os.path.join(cwd,custom_app,'migrations')
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

print('Detecting database changes...')
print('')
sleep(2)
make_migrations_output = subprocess.check_output(['python', 'manage.py', 'makemigrations'] + custom_apps)
print(make_migrations_output)
print('')

sleep(3)

print('Making database changes...')
print('')
sleep(2)
migrate_output = subprocess.check_output(['python', 'manage.py', 'migrate'])
print(migrate_output)
print('')

print('Creating Admin user...')
print ('')
sleep(2)
print(create_admin())
