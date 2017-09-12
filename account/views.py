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

from .models import Profile
from permission_admin.models import Dataset

from texta.settings import USER_MODELS, URL_PREFIX, INFO_LOGGER, USER_ISACTIVE_DEFAULT


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

    #user = authenticate(username=username, password=password)

    #if user is not None:
    #    django_login(request, user)

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
    request.user.set_password(request.POST['new_password'])

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
    return '%014x' % random.randrange(16**14)


@require_POST
def get_auth_token(request):
    try:
        _validate_user_auth_input(request)
    except Exception as input_error:
        return HttpResponse(json.dumps({'error': str(input_error)}))

    content_body = json.loads(request.body)
    user = authenticate(username=content_body['username'], password=content_body['password'])

    if user is not None:
        try:
            user.profile
        except:
            Profile.objects.create(user = user).save()

        auth_token = user.profile.auth_token

        if not auth_token:
            auth_token = _generate_random_token()
            user.profile.auth_token=auth_token
            user.save()

        return HttpResponse(json.dumps({'auth_token': auth_token}))
    else:
        return HttpResponse(json.dumps({'error': 'Unable to authenticate the user with the provided username and password combination.'}))


@require_POST
def revoke_auth_token(request):
    try:
        _validate_user_auth_input(request)
    except Exception as input_error:
        return HttpResponse(json.dumps({'error': str(input_error)}))

    content_body = json.loads(request.body)
    user = authenticate(username=content_body['username'], password=content_body['password'])

    if user is not None:
        try:
            user.profile.auth_token=''
            user.save()
        except:
            Profile.objects.create(user = user).save()

        return HttpResponse(json.dumps({'success': True}))
    else:
        return HttpResponse(json.dumps({'error': 'Unable to authenticate the user with the provided username and password combination.'}))


def _validate_user_auth_input(request):
    try:
        content_body = json.loads(request.body)
    except:
        raise Exception('Could not parse JSON.')

    try:
        content_body['username']
    except:
        raise Exception('Username missing.')

    try:
        content_body['password']
    except:
        raise Exception('Password missing.')
