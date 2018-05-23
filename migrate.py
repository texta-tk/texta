# TODO Add initial superuser credentials into the .env file and call its value in the command.
import django  # For making sure the correct Python environment is used.
from texta.settings import INSTALLED_APPS, DATABASES
import subprocess
import sys
import os
import shutil

CWD = os.path.realpath(os.path.dirname(__file__))


def create_admin():
	from django.contrib.auth.models import User
	u = User(username='admin')
	u.set_password('1234')
	u.is_superuser = True
	u.is_staff = True

	try:
		u.save()
		return True
	except Exception as e:
		print(e)
		return False


create_admin()
