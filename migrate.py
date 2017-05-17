import django # For making sure the correct Python environment is used.
from texta.settings import INSTALLED_APPS
import subprocess
from time import sleep

custom_apps = [app for app in INSTALLED_APPS if not app.startswith('django')] # Migration works for custom apps only. Manage.py can't detect relevant built-in django apps.

print('Detecting database changes...')
print('')
sleep(2)
make_migrations_output = subprocess.check_output(['python', 'manage.py', 'makemigrations'] + custom_apps)
print(make_migrations_output)
print('')
print('')

sleep(3)

print('Making database changes...')
print('')
sleep(2)
migrate_output = subprocess.check_output(['python', 'manage.py', 'migrate'])
print(migrate_output)
