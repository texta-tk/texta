import datetime
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse 
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from utils.datasets import Datasets
from task_manager.models import Task
from permission_admin.models import Dataset, ScriptProject
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL, URL_PREFIX, SCRIPT_MANAGER_DIR
from task_manager.tasks.task_types import TaskTypes

from permission_admin.script_runner import ScriptRunner
import multiprocessing

import os
import shutil

#remove 
from texta.settings import STATIC_URL, URL_PREFIX, INFO_LOGGER, ERROR_LOGGER
import logging

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_dataset(request):
    daterange = ""
    dataset = Dataset(author=request.user, index=request.POST['index'],
                      mapping=request.POST['mapping'], daterange=daterange, access=(request.POST['access']))
    dataset.save()

    create_dataset_access_permission_and_propagate(dataset, request.POST['access'])

    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


def create_dataset_access_permission_and_propagate(dataset, access):
    content_type = ContentType.objects.get_for_model(Dataset)
    permission = Permission.objects.create(
        codename='can_access_dataset_' + str(dataset.id),
        name='Can access dataset {0} -> {1}'.format(dataset.index, dataset.mapping),
        content_type=content_type,
    )
    permission.save()

    if access == 'public':
        for user in User.objects.all():
            user.user_permissions.add(permission)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_dataset(request):
    index_to_delete = request.POST['index']
    remove_dataset(index_to_delete)

    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_index(request):
    index_to_delete = request.POST['index']
    index_name = Dataset.objects.get(pk=index_to_delete).index

    remove_dataset(index_to_delete)
    es_m = ES_Manager.delete_index(index_name)

    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


def remove_dataset(index_to_delete):
    index_to_delete = Dataset.objects.get(pk=index_to_delete)

    content_type = ContentType.objects.get_for_model(Dataset)
    Permission.objects.get(
        codename='can_access_dataset_' + str(index_to_delete.id),
        content_type=content_type,
    ).delete()

    index_to_delete.delete()
    return True


@login_required
@user_passes_test(lambda u: u.is_superuser)
def open_close_dataset(request):
    dataset_id = request.POST['dataset_id']
    dataset = Dataset.objects.get(pk=dataset_id)

    if request.POST['open_close'] == 'open':
        ES_Manager.open_index(dataset.index)
    else:
        ES_Manager.close_index(dataset.index)

    return HttpResponse()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def index(request):
    try:
        indices = ES_Manager.get_indices()
        indices = sorted(indices, key=lambda x: x['index'])  # sort alphabetically
        datasets = get_datasets(indices=indices)
        users = User.objects.all()

        users = annotate_users_with_permissions(users, datasets)

        template = loader.get_template('permission_admin.html')

        allowed_datasets = Datasets().get_allowed_datasets(request.user)
        language_models = Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL).filter(status__iexact=Task.STATUS_COMPLETED).order_by('-pk')
        print(language_models)
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DEBUG ALL MODELS COMPLETED', 'data': [str(x) for x in language_models]}))
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DEBUG ALL MODELS LM', 'data': [str(x) for x in Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL)]}))
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DEBUG ALL MODELS STATUS', 'data': [str(x.status) for x in Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL)]}))
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DEBUG SANITY CHECK', 'data': 'test'}))
        for model in language_models:
            data = """
                pk: {}
                status: {}
                description: {}
                type: {}
            """.format(model.pk, model.status, model.description, model.task_type)
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DEBUG MODELS', 'data': data}))
    except:
        logging.getLogger(ERROR_LOGGER).error(
            json.dumps({'process': 'PERMISSION ADMIN INDEX', 'event': 'permission_admin_index_exception'}), exc_info=True)
    return HttpResponse(template.render({'users':users,'datasets':datasets,'indices':indices,'STATIC_URL':STATIC_URL,'URL_PREFIX':URL_PREFIX, 'allowed_datasets': allowed_datasets, 'language_models': language_models},request))

def annotate_users_with_permissions(users, datasets):
    new_users = []

    content_type = ContentType.objects.get_for_model(Dataset)

    for user in users:
        new_user = {key: getattr(user, key) for key in ['pk', 'username', 'email', 'last_login', 'is_superuser', 'is_active']}

        permissions = []
        restrictions = []

        for dataset in datasets:
            permission = Permission.objects.get(
                codename='can_access_dataset_' + str(dataset.pk),
                content_type=content_type
            )

            # permission.name[19:] skips prefix "Can access dataset " to save room in GUI
            if user.has_perm('permission_admin.' + permission.codename):
                permissions.append({'codename': permission.codename, 'name': permission.name[19:]})
            else:
                restrictions.append({'codename': permission.codename, 'name': permission.name[19:]})

        new_user['permissions'] = permissions
        new_user['restrictions'] = restrictions

        new_users.append(new_user)

    return new_users


def get_datasets(indices=None):
    datasets = Dataset.objects.all()
    datasets_out = []
    for dataset in datasets:
        ds_out = dataset.__dict__
        if indices:
            for index in indices:
                if index['index'] == ds_out['index']:
                    ds_out['status'] = index['status']
                    ds_out['docs_count'] = index['docs_count']
                    ds_out['store_size'] = index['store_size']
                elif '*' in ds_out['index']:
                    ds_out['status'] = 'open'
                    ds_out['docs_count'] = 'multiindex'
                    ds_out['store_size'] = 'multiindex'

        datasets_out.append(ds_out)

    return datasets


@login_required
@user_passes_test(lambda u: u.is_superuser)
def change_isactive(request):
    user_id = request.POST['user_id']
    change = request.POST['change']

    if change == 'activate':
        is_active = True
    else:
        is_active = False

    user = User.objects.get(pk=int(user_id))
    user.is_active = is_active
    user.save()

    return HttpResponse()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_user(request):
    user_id_to_delete = request.POST['user_id']
    user_to_delete = User.objects.get(pk=user_id_to_delete)
    user_to_delete.delete()
    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def change_permissions(request):
    user_id = request.POST['user_id']
    change = request.POST['change']

    if change == 'to_superuser':
        is_superuser = True
    else:
        is_superuser = False

    user = User.objects.get(pk=int(user_id))
    user.is_superuser = is_superuser
    user.save()

    return HttpResponse()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def get_mappings(request):
    index = request.GET['index']
    return HttpResponse(json.dumps(ES_Manager.get_mappings(index)))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_script_project(request):
    name = request.POST['name']
    desc = request.POST['description']
    entrance = request.POST['entrance']
    arguments = request.POST['arguments']

    sp = ScriptProject(name=name, desc=desc, entrance_point=entrance, arguments=arguments)
    sp.save()

    project_path = os.path.join(SCRIPT_MANAGER_DIR, '%s_%s' % (str(sp.id), canonize_project_name(name)))

    if not os.path.exists(project_path):
        os.makedirs(project_path)

    for file_ in request.FILES.getlist('files[]'):
        path = default_storage.save(os.path.join(project_path, file_.name), ContentFile(file_.read()))

    return HttpResponse()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def list_script_projects(request):
    script_projects = ScriptProject.objects.all()

    template = loader.get_template('script_manager/project_list.html')
    return HttpResponse(template.render({'projects': script_projects}, request))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def run_script_project(request):
    project_id = request.POST['project_id']

    script_project = ScriptProject.objects.get(pk=project_id)

    script_runner = ScriptRunner(script_project, SCRIPT_MANAGER_DIR)
    project_daemon = multiprocessing.Process(name='daemon', target=script_runner.run)

    script_runner.run()

    # project_daemon.daemon = True
    # project_daemon.start()

    return HttpResponse()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_script_project(request):
    project_id = request.POST['project_id']
    script_project = ScriptProject.objects.get(pk=project_id)

    project_path = os.path.join(SCRIPT_MANAGER_DIR,
                                '%s_%s' % (str(script_project.id), canonize_project_name(script_project.name)))
    # project_path = os.path.join(SCRIPT_MANAGER_DIR, canonize_project_name(script_project.name))

    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    script_project.delete()

    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


@user_passes_test(lambda u: u.is_superuser)
def update_dataset_permissions(request):
    allowed_codenames = json.loads(request.POST['allowed'])
    disallowed_codenames = json.loads(request.POST['disallowed'])
    user_id = request.POST['user_id']

    user = User.objects.get(pk=user_id)
    content_type = ContentType.objects.get_for_model(Dataset)

    for allowed_codename in allowed_codenames:
        permission = Permission.objects.get(
            codename=allowed_codename,
            content_type=content_type
        )
        user.user_permissions.add(permission)

    for disallowed_codename in disallowed_codenames:
        permission = Permission.objects.get(
            codename=disallowed_codename,
            content_type=content_type
        )
        user.user_permissions.remove(permission)

    return HttpResponse()


def canonize_project_name(name):
    return name.lower().replace(' ', '_')


def _pickle_method(method):
    func_name = method.__func__.__name__
    obj = method.__self__
    cls = method.__self__.__class__
    return _unpickle_method, (func_name, obj, cls)


def _unpickle_method(func_name, obj, cls):
    for cls in cls.mro():
        try:
            func = cls.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)


import copyreg 
import types

copyreg.pickle(types.MethodType, _pickle_method, _unpickle_method) 
