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

BACKUP_STRFTIME_FORMAT = '%Y-%m-%d %H-%M-%S'
BACKUP_DATE_PATTERN = re.compile('pre-(\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})')


def database_exists():
    database_path = DATABASES['default']['NAME']
    return os.path.exists(database_path)


def backup_existing_database():
    database_path = DATABASES['default']['NAME']
    database_dir, database_name = os.path.split(database_path)

    backupped_database_substring = datetime.datetime.now().strftime('pre-' + BACKUP_STRFTIME_FORMAT)
    backup_database_name_components = database_name.split('.')
    backup_database_name_components.insert(-1, backupped_database_substring)

    shutil.copy2(database_path, os.path.join(database_dir, '.'.join(backup_database_name_components)))


def remove_too_old_database_versions():
    database_dir = os.path.dirname(DATABASES['default']['NAME'])
    old_database_files = glob.glob(os.path.join(database_dir, '*.pre-*'))
    ts_and_database_filenames = []

    for filename in old_database_files:
        dt_object = datetime.datetime.strptime(BACKUP_DATE_PATTERN.search(filename).group(1), BACKUP_STRFTIME_FORMAT)
        timestamp = time.mktime(dt_object.timetuple())
        ts_and_database_filenames.append((timestamp, filename))

    ts_and_database_filenames.sort(key=operator.itemgetter(0), reverse=True)
    removed_files = ts_and_database_filenames[DATABASES['default']['BACKUP_COUNT']:]

    for removed_file in removed_files:
        os.remove(removed_file[1])


if database_exists():
    print('Backupping existing database...')
    backup_existing_database()
    sleep(2)

print('Removing too old database versions...')
remove_too_old_database_versions()

sleep(2)

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
make_migrations_output = subprocess.check_output(['python3', 'manage.py', 'makemigrations'] + custom_apps)
print(make_migrations_output)
print('')

sleep(3)

print('Making database changes...')
print('')
sleep(2)
migrate_output = subprocess.check_output(['python3', 'manage.py', 'migrate'])
print(migrate_output)
