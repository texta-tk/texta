# -*- coding:utf-8 -*-
import json
import logging
import os
from collections import defaultdict
import random

from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_POST
from django.template import loader
from django.core.mail import EmailMessage
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import EmailMessage
from .models import Profile
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from task_manager.models import Task
from task_manager.tasks.task_types import TaskTypes

from texta.settings import REQUIRE_EMAIL_CONFIRMATION, USER_MODELS, URL_PREFIX, INFO_LOGGER, USER_ISACTIVE_DEFAULT, es_url, STATIC_URL


def index(request):
	template = loader.get_template('account.html')
	datasets = Datasets().get_allowed_datasets(request.user)
	language_models =Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL.value).filter(status__iexact=Task.STATUS_COMPLETED).order_by('-pk')

	return HttpResponse(
			template.render({'STATIC_URL': STATIC_URL, 'allowed_datasets': datasets, 'language_models': language_models}, request))

@login_required
def update_dataset(request):
	logger = LogManager(__name__, 'CHANGE_SETTINGS')
	parameters = request.POST
	try:
		# TODO: check if is a valid mapping_id before change session[dataset]
		new_datasets = parameters.getlist('dataset[]')
		new_datasets = [new_dataset for new_dataset in new_datasets if request.user.has_perm('permission_admin.can_access_dataset_' + str(new_dataset))]
		request.session['dataset'] = new_datasets

		logger.clean_context()
		logger.set_context('user_name', request.user.username)
		logger.set_context('new_datasets', new_datasets)
		logger.info('datasets_updated')

		ds = Datasets().activate_datasets(request.session)
		return HttpResponse(json.dumps({'status': 'success'}))
	except:
		return HttpResponse(json.dumps({'status': 'error'}))


@login_required
def update_model(request):
	logger = LogManager(__name__, 'CHANGE_SETTINGS')
	parameters = request.POST
	try:
		model = {"pk": parameters["model_pk"], "description": parameters["model_description"], "unique_id": parameters["model_uuid"]}
		request.session['model'] = model
		logger.clean_context()
		logger.set_context('user_name', request.user.username)
		logger.set_context('new_model', model)
		logger.info('model_updated')
		return HttpResponse(json.dumps({'status': 'success'}))
	except:
		return HttpResponse(json.dumps({'status': 'error'}))


### MANAGING ACCOUNTS ###
def _send_confirmation_email(user,email):
	if(REQUIRE_EMAIL_CONFIRMATION):
		token=_generate_random_token()
		email = EmailMessage('Email Confirmation', 'Please confirm your email by clicking this link:'+URL_PREFIX+'/confirm/'+token, to=[email])
	
		try:
			user.profile
		except:
			Profile.objects.create(user=user).save()

		user.profile.email_confirmation_token = token
		user.save()
		email.send()


def create(request):
	username = request.POST['username']
	password = request.POST['password']
	email = request.POST['email']

	issues = validate_form(username, password, email)
	if len(issues):
		return HttpResponse(json.dumps({'url': '#', 'issues': issues}))

	user = User.objects.create_user(username, email, password)
	_send_confirmation_email(user,email)

	if USER_ISACTIVE_DEFAULT == False:
		user.is_active = False
		user.save()
		

	if user:
		initialize_permissions(user)

	user_path = os.path.join(USER_MODELS, username)
	if not os.path.exists(user_path):
		os.makedirs(user_path)
		
	logging.getLogger(INFO_LOGGER).info(json.dumps(
			{'process': 'CREATE USER', 'event': 'create_user', 'args': {'user_name': username, 'email': email}}))

	if USER_ISACTIVE_DEFAULT == True:
		user = authenticate(username=username, password=password)	
		if user is not None:
			django_login(request, user)

	return HttpResponse(json.dumps({'url': (URL_PREFIX + '/'), 'issues': {}}))


def initialize_permissions(user):
	content_type = ContentType.objects.get_for_model(Dataset)

	for dataset in Dataset.objects.filter(access='public'):
		permission = Permission.objects.get(
				codename='can_access_dataset_' + str(dataset.id),
				content_type=content_type,
		)
		user.user_permissions.add(permission)


def validate_form(username, password, email):
	issues = defaultdict(list)
	if len(username) < 3:
		issues['username'].append('Username too short.')
	if User.objects.filter(username=username).exists():
		issues['username'].append('Username exists.')

	return dict(issues)


@login_required
def change_password(request):
	user = User.objects.get(username__exact=request.user)
	user.set_password(request.POST['new_password'])
	user.save()
	django_login(request, user)

	return HttpResponse()

def login(request):
	username = request.POST['username']
	password = request.POST['password']

	user = authenticate(username=username, password=password)

	if user is not None:
		django_login(request, user)
		logging.getLogger(INFO_LOGGER).info(
				json.dumps({'process': '*', 'event': 'login_process_succeeded', 'args': {'user_name': username}}))
		return HttpResponse(json.dumps({'process': '*', 'event': 'login_process_succeeded', 'args': {'user_name': username}}))

	else:
		logging.getLogger(INFO_LOGGER).info(
				json.dumps({'process': '*', 'event': 'login_process_failed', 'args': {'user_name': username}}))

	return HttpResponse(json.dumps({'process': '*', 'event': 'login_process_failed', 'args': {'user_name': username}}), status=401)


@login_required
def log_out(request):
	django_logout(request)
	logging.getLogger(INFO_LOGGER).info(
			json.dumps({'process': '*', 'event': 'logout', 'args': {'user_name': request.user.username}}))
	return HttpResponseRedirect(URL_PREFIX + '/')


def _generate_random_token():
	return '%014x' % random.randrange(16 ** 14)


@require_POST
def get_auth_token(request):
	try:
		_validate_user_auth_input(request)
	except ValueError as input_error:
		return HttpResponse(json.dumps({'error': str(input_error)}))

	content_body = json.loads(request.body.decode("utf-8"))
	user = authenticate(username=content_body['username'], password=content_body['password'])

	if user is not None:
		try:
			user.profile
		except:
			Profile.objects.create(user=user).save()

		auth_token = user.profile.auth_token

		if not auth_token:
			auth_token = _generate_random_token()
			user.profile.auth_token = auth_token
			user.save()

		return HttpResponse(json.dumps({'auth_token': auth_token}))
	else:
		return HttpResponse(json.dumps(
				{'error': 'Unable to authenticate the user with the provided username and password combination.'}))


@require_POST
def revoke_auth_token(request):
	try:
		_validate_user_auth_input(request)
	except Exception as input_error:
		return HttpResponse(json.dumps({'error': str(input_error)}))

	content_body = json.loads(request.body.decode("utf-8"))
	user = authenticate(username=content_body['username'], password=content_body['password'])

	if user is not None:
		try:
			user.profile.auth_token = ''
			user.save()
		except:
			Profile.objects.create(user=user).save()

		return HttpResponse(json.dumps({'success': True}))
	else:
		return HttpResponse(json.dumps(
				{'error': 'Unable to authenticate the user with the provided username and password combination.'}))


def _validate_user_auth_input(request):
	try:
		content_body = json.loads(request.body.decode("utf-8"))
	except:
		content_body = json.loads(request.body.decode("utf-8"))
		raise ValueError('Could not parse JSON: {0}'.format())

	try:
		content_body['username']
	except:
		raise KeyError('Username missing.')

	try:
		content_body['password']
	except:
		raise KeyError('Password missing.')

def confirm_email(request, email_auth_token):
	template = loader.get_template('email-confirmation.html')
	
	profile = Profile.objects.get(email_confirmation_token=email_auth_token)
	if(profile.email_confirmed == False):	
		profile.email_confirmed=True
		profile.save()


		template_params={
			profile.user.username,
			profile.user.password,
			profile.user.email,
			profile.auth_token,
			profile.email_confirmation_token,
			str(profile.email_confirmed),
		}
		return HttpResponse(
				template.render( {'user_data': template_params}, request))
	else:
		return HttpResponseRedirect(URL_PREFIX + '/')
