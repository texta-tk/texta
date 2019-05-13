import django # For making sure the correct Python environment is used.
from django.db import connections
from django.db.utils import OperationalError
from toolkit.settings import INSTALLED_APPS
import subprocess
from time import sleep
import sys
import os
import shutil
import logging
import json

BASE_APP_NAME = "toolkit"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", BASE_APP_NAME+".settings")
django.setup()
from django.contrib.auth.models import User


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


def check_mysql_connection():
    db_conn = connections['default']
    try:
        c = db_conn.cursor()
    except OperationalError:
        connected = False
    else:
        connected = True
    return connected


def migrate(custom_apps):
    log_message = 'Toolkit: Detecting database changes.'
    print(log_message)
    make_migrations_output = subprocess.check_output(['python', 'manage.py', 'makemigrations'] + custom_apps)
    log_message = 'Toolkit: Making database changes.'
    print(log_message)
    sleep(2)
    migrate_output = subprocess.check_output(['python', 'manage.py', 'migrate'])
    log_message = 'Toolkit: Creating Admin user if necessary.'
    print(log_message)
    sleep(2)
    result = create_admin()
    log_message = 'New admin created: {}'.format(result)
    print(log_message)
    return True

# CREATE LIST OF CUSTOM APPS
cwd = os.path.realpath(os.path.dirname(__file__))
custom_apps = [app.split('.')[-1] for app in INSTALLED_APPS if app.startswith(BASE_APP_NAME)] # Migration works for custom apps only. Manage.py can't detect relevant built-in django apps.
print(INSTALLED_APPS)
print(custom_apps)

# DELETE MIGRATIONS IF ASKED
if len(sys.argv) > 1:
    if sys.argv[1] == 'purge_migrations':
        print('Deleting migrations...')
        for custom_app in custom_apps:
            migrations_dir = os.path.join(cwd, BASE_APP_NAME, custom_app, 'migrations')
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

# CONNECT TO DATABASE & MIGRATE
connected = False
n_try = 0
while connected == False and n_try <= 10:
    connected = check_mysql_connection()
    if connected:
        migrate(custom_apps)
    else:
        n_try += 1
        print('Toolkit migration attempt {}: No connection to database. Sleeping for 10 sec and trying again.'.format(n_try))
        sleep(10)
