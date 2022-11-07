#! /usr/bin/env python3

import argparse
import os
import uuid
from time import sleep

import django  # For making sure the correct Python environment is used.
from django.core import management
from django.db import connections
from django.db.utils import OperationalError

parser = argparse.ArgumentParser()
parser.add_argument("-u", "--username", help="Name of the admin user to create.", default="admin")
parser.add_argument("-o", "--overwrite", action='store_true', help="Whether to overwrite the admin users password with what's set in 'TEXTA_ADMIN_PASSWORD'")
parser.set_defaults(overwrite=False)

args = parser.parse_args()

BASE_APP_NAME = "toolkit"
TEXTA_ADMIN_PASSWORD = os.getenv("TEXTA_ADMIN_PASSWORD", uuid.uuid4().hex)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", BASE_APP_NAME + ".settings")
django.setup()

from django.contrib.auth.models import User
from toolkit.core.core_variable.models import CoreVariable
from toolkit.core.choices import CORE_VARIABLE_CHOICES


def create_admin(arguments: argparse.Namespace):
    user, is_freshly_created = User.objects.get_or_create(username=arguments.username)
    user.is_superuser = True
    user.is_staff = True

    if is_freshly_created:
        user.set_password(TEXTA_ADMIN_PASSWORD)
        log_message = f"Toolkit: Admin user password is: {TEXTA_ADMIN_PASSWORD}"
        print(log_message)

    if arguments.overwrite and is_freshly_created is False:
        password = os.getenv("TEXTA_ADMIN_PASSWORD", None)
        if password:
            user.set_password(password)
            log_message = f"Toolkit: New admin user password is: {password}"
            print(log_message)
        else:
            print("Toolkit: No password was set inside 'TEXTA_ADMIN_PASSWORD' for overwrite.")

    user.save()
    return is_freshly_created


def check_mysql_connection():
    db_conn = connections['default']
    try:
        c = db_conn.cursor()
    except OperationalError:
        connected = False
    else:
        connected = True
    return connected


def migrate(arguments: argparse.Namespace):
    log_message = 'Toolkit: Applying migrations.'
    print(log_message)

    management.call_command('migrate', verbosity=3)
    log_message = 'Toolkit: Creating Admin user if necessary.'
    print(log_message)
    sleep(2)
    result = create_admin(arguments)
    log_message = 'Toolkit: Admin created: {}'.format(result)
    print(log_message)
    return True


def wait_for_connect(try_count=10, wait_timer=10):
    # CONNECT TO DATABASE & MIGRATE
    connected = False
    n_try = 0
    while connected is False and n_try <= try_count:
        connected = check_mysql_connection()
        if connected:
            return
        else:
            n_try += 1
            print('Toolkit migration attempt {}: No connection to database. Sleeping for 10 sec and trying again.'.format(n_try))
            sleep(wait_timer)


def initialize_core_variables():
    # CREATE CORE VARIABLE ENTRIES TO DB
    log_message = 'Toolkit: Adding empty core variables to database if needed.'
    print(log_message)

    for core_variable_choice in CORE_VARIABLE_CHOICES:
        variable_name = core_variable_choice[0]
        matching_variables = CoreVariable.objects.filter(name=variable_name)
        # if core variable not present in db
        if not matching_variables:
            new_core_variable = CoreVariable(name=variable_name, value=None)
            new_core_variable.save()


if __name__ == '__main__':
    wait_for_connect()
    migrate(args)
    initialize_core_variables()
