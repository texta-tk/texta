
import os
import json
import logging
from datetime import datetime

# from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect, QueryDict
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from task_manager.models import Task
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL
from texta.settings import URL_PREFIX
from texta.settings import MODELS_DIR
from texta.settings import ERROR_LOGGER
from account.models import Profile

from dataset_importer.document_preprocessor import preprocessor_map
# from .language_model_manager.language_model_manager import LanguageModel
# from .tag_manager.tag_manager import TaggingModel, get_pipeline_builder
# from task_manager.tasks import Preprocessor
# from .models import Task

from task_manager.tasks.task_params import task_params
from task_manager.tools import get_pipeline_builder


def get_fields(es_m):
    """ Create field list from fields in the Elasticsearch mapping
    """
    illegal_paths = ['texta_facts']
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        path = data['path']
        if path not in illegal_paths:
            path_list = path.split('.')
            label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
            label = label.replace('-->', u'→')
            field = {'data': json.dumps(data), 'label': label, 'path': path}
            fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])
    return fields


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        if key == 'text_tagger':
            value['enabled_taggers'] = Task.objects.filter(task_type='train_tagger').filter(status__iexact='completed')
        value['key'] = key
        entries.append(value)

    return entries


@login_required
def index(request):
    ds = Datasets().activate_dataset(request.session)
    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status__iexact='completed').order_by('-pk')

    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)

    preprocessors = collect_map_entries(preprocessor_map)
    enabled_preprocessors = [preprocessor for preprocessor in preprocessors if preprocessor['is_enabled'] is True]

    tasks = []

    for task in Task.objects.all().order_by('-pk'):
        task_dict = task.__dict__
        task_dict['user'] = task.user
        task_dict['parameters'] = translate_parameters(task_dict['parameters'])

        if task_dict['result']:
            task_dict['result'] = json.loads(task_dict['result'])

        tasks.append(task_dict)

    if 'dataset' in request.session.keys():
        context = {
            'task_params':           task_params,
            'tasks':                 tasks,
            'language_models':       language_models,
            'allowed_datasets':      datasets,
            'searches':              Search.objects.filter(dataset=Dataset(pk=int(request.session['dataset']))),  # Search.objects.filter(author=request.user, dataset=Dataset(pk=int(request.session['dataset']))),
            'enabled_preprocessors': enabled_preprocessors,
            'STATIC_URL':            STATIC_URL,
            'fields':                fields
        }
    else:
        return HttpResponseRedirect('/')

    pipe_builder = get_pipeline_builder()
    context['train_tagger_extractor_opt_list'] = pipe_builder.get_extractor_options()
    context['train_tagger_reductor_opt_list'] = pipe_builder.get_reductor_options()
    context['train_tagger_normalizer_opt_list'] = pipe_builder.get_normalizer_options()
    context['train_tagger_classifier_opt_list'] = pipe_builder.get_classifier_options()

    template = loader.get_template('task_manager.html')
    return HttpResponse(template.render(context, request))


def translate_parameters(params):
    pipe_builder = get_pipeline_builder()

    datasets = Datasets().datasets

    # preprocessors = collect_map_entries(preprocessor_map)
    # enabled_taggers = [preprocessor for preprocessor in preprocessors if preprocessor['is_enabled'] is True and preprocessor['key'] is 'text_tagger'][0]['enabled_taggers']
    # enabled_taggers = {enabled_tagger.pk: enabled_tagger.description for enabled_tagger in enabled_taggers}
    # TODO: remove this
    enabled_taggers = {}

    extractor_options = {a['index']: a['label'] for a in pipe_builder.get_extractor_options()}
    reductor_options = {a['index']: a['label'] for a in pipe_builder.get_reductor_options()}
    normalizer_options = {a['index']: a['label'] for a in pipe_builder.get_normalizer_options()}
    classifier_options = {a['index']: a['label'] for a in pipe_builder.get_classifier_options()}

    translations = {'search': {'type': 'url', 'pattern': '<a href="' + URL_PREFIX + '/searcher?search={0}" target="_blank">{0}</a>'},
                    'extractor_opt': {'type': 'dict', 'pattern': extractor_options},
                    'reductor_opt': {'type': 'dict', 'pattern': reductor_options},
                    'normalizer_opt': {'type': 'dict', 'pattern': normalizer_options},
                    'classifier_opt': {'type': 'dict', 'pattern': classifier_options},
                    'dataset': {'type': 'dict', 'pattern': datasets},
                    'text_tagger_taggers': {'type': 'list', 'pattern': enabled_taggers}}

    params = json.loads(params)

    for k, v in params.items():
        if k in translations:
            params[k] = translate_param(translations[k], v)

    return params


def translate_param(translation, value):
    if translation['type'] == 'url':
        return translation['pattern'].format(value)
    elif translation['type'] == 'dict':
        try:
            return translation['pattern'][int(value)]
        except KeyError:
            return '{0}: Dataset missing'.format(value)
    elif translation['type'] == 'list':
        return [translation['pattern'][int(list_item)] for list_item in value if int(list_item) in translation['pattern']]


@login_required
def start_task(request):
    user = request.user
    task_type = request.POST['task_type']
    task_params = filter_params(request.POST)
    description = task_params['description']

    if 'dataset' in request.session.keys():
        task_params['dataset'] = int(request.session['dataset'])

    # TODO: eliminate the need of this special treatment ?
    if task_type == 'apply_preprocessor':
        task_params = filter_preprocessor_params(request.POST, task_params)

    # Create execution task
    task_id = create_task(task_type, description, task_params, user)
    # Add task to queue
    task = Task.get_by_id(task_id)
    task.update_status(Task.STATUS_QUEUED)

    return HttpResponse()


@login_required
def delete_task(request):
    """
    Deletes instance of the Task model from the database
    and the model.pickle from the filesystem.

    :param request:
    :return:
    """
    task_id = int(request.POST['task_id'])
    task = Task.objects.get(pk=task_id)

    if 'train' in task.task_type:
        try:
            file_path = os.path.join(MODELS_DIR, "model_" + str(task_id))
            os.remove(file_path)
        except Exception:
            file_path = os.path.join(MODELS_DIR, "model_" + str(task_id))
            logging.getLogger(ERROR_LOGGER).error('Could not delete model.', extra={'file_path': file_path})

    task.delete()
    return HttpResponse()


@login_required
def download_model(request):
    """
    Sends model.pickle as a download response to the end-user if it exists in the filesystem,
    if not, sends an empty response.

    :param request:
    :return:
    """
    model_id = request.GET['model_id']
    file_path = os.path.join(MODELS_DIR, "model_" + str(model_id))

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh)
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(file_path)
            return response

    return HttpResponse()


def _api_token_auth(auth_token):
    try:
        profile = Profile.objects.get(auth_token=auth_token)
        user = profile.user
        valid_token = True
    except Profile.DoesNotExist:
        user = None
        valid_token = False
    return user, valid_token


def api_info(request):
    """
    """
    data = {'name': 'TEXTA Task Manager API',
            'version': '1.0'}

    data_json = json.dumps(data)
    return HttpResponse(data_json, content_type='application/json')


def api_get_task_list(request):
    """
    """
    request_data = request.body.decode("utf-8")
    params = json.loads(request_data)
    auth_token = params.get('auth_token', None)
    user, valid_token = _api_token_auth(auth_token)

    if valid_token:
        tasks = Task.objects.all()
        data = []
        # Build task list
        for task in tasks:
            t = {
                'task_id': task.id,
                'task_type': task.task_type,
                'status': task.status,
                'user': task.user.username
            }
            data.append(t)
        data_json = json.dumps(data)
        return HttpResponse(data_json, content_type='application/json')
    else:
        error = {'error': 'not authorized'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=403, content_type='application/json')


def api_get_task_status(request):
    """
    """
    request_data = request.body.decode("utf-8")
    params = json.loads(request_data)
    auth_token = params.get('auth_token', None)
    user, valid_token = _api_token_auth(auth_token)

    if valid_token:

        task_id = params.get('task_id', None)
        try:
            task = Task.get_by_id(task_id)
            data = task.to_json()
            data_json = json.dumps(data)
            return HttpResponse(data_json, status=200, content_type='application/json')
        except Task.DoesNotExist as e:
            error = {'error': 'task id is not valid'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')
    else:
        error = {'error': 'not authorized'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=403, content_type='application/json')


def api_train_model(request):
    """
    """
    try:
        task_type = "train_model"
        request_data = request.body.decode("utf-8")
        params = json.loads(request_data)
        auth_token = params.get('auth_token', None)
        user, valid_token = _api_token_auth(auth_token)

        if valid_token:
            request_data = request.body.decode("utf-8")
            params = json.loads(request_data)
            description = params['description']
            # Create execution task
            task_id = create_task(task_type, description, params, user)
            # Add task to queue
            task = Task.get_by_id(task_id)
            task.update_status(Task.STATUS_QUEUED)
            # Return reference to task
            data = {
                'task_id': task_id,
                'task_type': task_type,
                'status': task.status,
                'user': task.user.username
            }
            data_json = json.dumps(data)
            return HttpResponse(data_json, status=200, content_type='application/json')

        else:
            error = {'error': 'not authorized'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=403, content_type='application/json')

    except Exception as e:
        print(e)
        error = {'error': 'invalid request'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')


def api_train_tagger(request):
    """
    """
    try:
        task_type = "train_tagger"
        request_data = request.body.decode("utf-8")
        params = json.loads(request_data)
        auth_token = params.get('auth_token', None)
        user, valid_token = _api_token_auth(auth_token)

        if valid_token:
            request_data = request.body.decode("utf-8")
            params = json.loads(request_data)
            description = params['description']
            # Create execution task
            task_id = create_task(task_type, description, params, user)
            # Add task to queue
            task = Task.get_by_id(task_id)
            task.update_status(Task.STATUS_QUEUED)
            # Return reference to task
            data = {
                'task_id': task_id,
                'task_type': task_type,
                'status': task.status,
                'user': task.user.username
            }
            data_json = json.dumps(data)
            return HttpResponse(data_json, status=200, content_type='application/json')

        else:
            error = {'error': 'not authorized'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=403, content_type='application/json')

    except Exception as e:
        print(e)
        error = {'error': 'invalid request'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')


def api_apply(request):
    """
    """
    try:
        task_type = "apply_preprocessor"
        request_data = request.body.decode("utf-8")
        params = json.loads(request_data)
        auth_token = params.get('auth_token', None)
        user, valid_token = _api_token_auth(auth_token)

        if valid_token:
            description = params['description']
            # Create execution task
            task_id = create_task(task_type, description, params, user)
            # Add task to queue
            task = Task.get_by_id(task_id)
            task.update_status(Task.STATUS_QUEUED)
            # Return reference to task
            data = {
                'task_id': task_id,
                'task_type': task_type,
                'status': task.status,
                'user': task.user.username
            }
            data_json = json.dumps(data)
            return HttpResponse(data_json, status=200, content_type='application/json')

        else:
            error = {'error': 'not authorized'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=403, content_type='application/json')

    except Exception as e:
        print(e)
        error = {'error': 'invalid request'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')


def create_task(task_type: str, description: str, parameters: dict, user: User) -> int:
    """
    Creates a db entry for the Task model and returns it's model.ID

    :param task_type: Specifies type of the task for ex. train_tagger, train_model, apply_preprocessor.
    :param description: User specified description to identify the task.
    :param parameters: Form data send from the page.
    :param user:
    :return: Id of created Task model entry.
    """
    # Creates a db entry for new task and returns task ID
    new_task = Task(description=description,
                    task_type=task_type,
                    parameters=json.dumps(parameters),
                    status=Task.STATUS_CREATED,
                    time_started=datetime.now(),
                    last_update=datetime.now(),
                    time_completed=None,
                    result='',
                    user=user)
    new_task.save()
    return new_task.pk


def filter_params(post: QueryDict):
    """
    Because ALL of the form data from the page is sent to the server,
    including the Task types you did not want, filtering them is necessary.

    ex. apply_preprocessor_description or train_model_dataset etc.

    :param post: Django POST input in the form of a QueryDict.
    :return: Form data relevant to the actual Task type being invoked.
    """
    prefix = post['task_type']
    filtered_params = {}

    for param in post:
        if param.startswith(prefix):
            filtered_params[param[len(prefix) + 1:]] = post[param]

    if 'description' not in filtered_params:
        filtered_params['description'] = ''

    return filtered_params


def filter_preprocessor_params(post, filtered_params):
    prefix = post['apply_preprocessor_preprocessor_key']

    for param in post:
        if param.startswith(prefix):
            filtered_params[param] = post.getlist(param)

    return filtered_params
