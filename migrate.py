import django # For making sure the correct Python environment is used.
from texta.settings import INSTALLED_APPS
import subprocess
from time import sleep
import sys
import os


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texta.settings")
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


def migrate(custom_apps):
    print('Toolkit: Detecting database changes.')
    make_migrations_output = subprocess.check_output(['python', 'manage.py', 'makemigrations'] + custom_apps)
    print('Toolkit: Making database changes.')
    sleep(2)
    migrate_output = subprocess.check_output(['python', 'manage.py', 'migrate'])
    print('Toolkit: Creating Admin user if necessary.')
    sleep(2)
    create_admin()
    return True


cwd = os.path.realpath(os.path.dirname(__file__))
custom_apps = [app for app in INSTALLED_APPS if not app.startswith('django')] # Migration works for custom apps only. Manage.py can't detect relevant built-in django apps.

if len(sys.argv) > 1:
    if sys.argv[1] == 'purge_migrations':
        print('Deleting migrations...')
        for custom_app in custom_apps:
            migrations_dir = os.path.join(cwd,custom_app,'migrations')
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

try:
    migrate(custom_apps)
except Exception:
    print('Migrations failed - MySQL possibly not ready yet. Sleeping for 10 sec & trying again.')
    sleep(10)
    migrate(custom_apps)
