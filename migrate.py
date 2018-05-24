import django  # For making sure the correct Python environment is used.
from texta.settings import INSTALLED_APPS, DATABASES
import sys
import os
import shutil

# Migration works for custom apps only. Manage.py can't detect relevant built-in django apps.
cwd = os.path.realpath(os.path.dirname(__file__))
custom_apps = [app for app in INSTALLED_APPS if not app.startswith('django')]

if len(sys.argv) > 1:
	if sys.argv[1] == 'purge_migrations':
		print('Deleting migrations...')
		for custom_app in custom_apps:
			migrations_dir = os.path.join(cwd, custom_app, 'migrations')
			if os.path.exists(migrations_dir):
				shutil.rmtree(migrations_dir)
