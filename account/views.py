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

from .models import Profile
from permission_admin.models import Dataset
from model_manager.models import ModelRun
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from task_manager.models import Task

from texta.settings import USER_MODELS, URL_PREFIX, INFO_LOGGER, USER_ISACTIVE_DEFAULT, es_url, STATIC_URL


def sort_datasets(datasets, indices):
	out = []

	open_indices = [index['index'] for index in indices if index['status'] == 'open']

	for dataset in sorted(datasets.items(), key=lambda l: l[1]['index']):
		ds = dataset[1]
		ds['id'] = dataset[0]
		if ds['index'] in open_indices:
			out.append(ds)
	return out


def get_allowed_datasets(datasets, user):
	return [dataset for dataset in datasets if
	        user.has_perm('permission_admin.can_access_dataset_' + str(dataset['id']))]


def index(request):
	indices = ES_Manager.get_indices()

	template = loader.get_template('account.html')
	ds = Datasets().activate_dataset(request.session)
	datasets = sort_datasets(ds.get_datasets(), indices)
	datasets = get_allowed_datasets(datasets, request.user)

	# TODO: We should check if the model is actually present on the disk
	language_models = Task.objects.filter(task_type='train_model').filter(status='completed').order_by('-pk')
	
	try:
		request.session['model']
	except KeyError:
		if len(language_models):
			request.session['model'] = str(language_models[0].id)

	return HttpResponse(
			template.render({'STATIC_URL': STATIC_URL, 'datasets': datasets, 'models': language_models}, request))


@login_required
def update(request):
	logger = LogManager(__name__, 'CHANGE_SETTINGS')

	parameters = request.POST

	if 'model' in parameters:
		model = str(parameters['model'])
		request.session['model'] = model
		logger.clean_context()
		logger.set_context('user_name', request.user.username)
		logger.set_context('new_model', model)
		logger.info('dataset_updated')

	if 'dataset' in parameters:
		# TODO: check if is a valid mapping_id before change session[dataset]
		new_dataset = parameters['dataset']

		if request.user.has_perm('permission_admin.can_access_dataset_' + str(new_dataset)):
			request.session['dataset'] = new_dataset

			logger.clean_context()
			logger.set_context('user_name', request.user.username)
			logger.set_context('new_dataset', new_dataset)
			logger.info('dataset_updated')

		ds = Datasets().activate_dataset(request.session)
		es_m = ds.build_manager(ES_Manager)

	return HttpResponseRedirect(URL_PREFIX + '/')


### MANAGING ACCOUNTS ###

def create(request):
	username = request.POST['username']
	password = request.POST['password']
	email = request.POST['email']

	issues = validate_form(username, password, email)
	if len(issues):
		return HttpResponse(json.dumps({'url': '#', 'issues': issues}))

	user = User.objects.create_user(username, email, password)

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

	return HttpResponseRedirect('/')


def login(request):
	username = request.POST['username']
	password = request.POST['password']

	user = authenticate(username=username, password=password)

	if user is not None:
		django_login(request, user)
		logging.getLogger(INFO_LOGGER).info(
				json.dumps({'process': '*', 'event': 'login_process_succeeded', 'args': {'user_name': username}}))
	else:
		logging.getLogger(INFO_LOGGER).info(
				json.dumps({'process': '*', 'event': 'login_process_failed', 'args': {'user_name': username}}))

	return HttpResponseRedirect(URL_PREFIX + '/')


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
