import json
from task_manager.models import Task
from django.http import HttpResponse
from account.api_auth import api_auth

from utils.datasets import Datasets
from permission_admin.models import Dataset
from searcher.models import Search
from utils.es_manager import ES_Manager

from task_manager.task_manager import create_task
from task_manager.task_manager import get_fields
from task_manager.tasks.workers.tag_model_worker import TagModelWorker
from task_manager.tools import MassHelper
from task_manager.tools import get_pipeline_builder


def api_info(request):
    """
    """
    data = {'name': 'TEXTA Task Manager API',
            'version': '1.0'}

    data_json = json.dumps(data)
    return HttpResponse(data_json, content_type='application/json')


@api_auth
def api_get_task_list(request, user, params):
    """
    """
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


@api_auth
def api_get_task_status(request, user, params):
    """
    """
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


@api_auth
def api_train_model(request, user, params):
    """
    """
    task_type = "train_model"
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


@api_auth
def api_train_tagger(request, user, params):
    """
    """
    task_type = "train_tagger"
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


@api_auth
def api_apply(request, user, params):
    """
    """
    task_type = "apply_preprocessor"
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


@api_auth
def api_dataset_list(request, user, params):
    """ Get list of available datasets for API user (via auth_token)
    """
    datasets = Datasets()
    dataset_mapping = datasets.get_allowed_datasets(user)
    data = []
    for d in dataset_mapping:
        # Build response structure
        row = {
            'dataset': d['id'],
            'index': d['index'],
            'mapping': d['mapping']
        }
        data.append(row)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_search_list(request, user, params):
    """ Get list of available searches for API user (via auth_token)
    """

    # Read all params
    dataset_id = int(params['dataset'])

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)
    # Check if dataset_id is valid
    if not ds.is_active():
            error = {'error': 'invalid dataset parameter'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')

    # Build response structure
    data = []
    dataset = Dataset(pk=dataset_id)
    search_list = list(Search.objects.filter(dataset=dataset))
    for search in search_list:
        row = {
            'dataset': dataset_id,
            'search': search.id,
            'description': search.description
        }
        data.append(row)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_normalizer_list(request, user, params):
    """ Get list of available normalizers for API user (via auth_token)
    """
    pipe_builder = get_pipeline_builder()

    data = []
    for opt in pipe_builder.get_normalizer_options():
        doc = {'normalizer_opt': opt['index'], 'label': opt['label']}
        data.append(doc)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_classifier_list(request, user, params):
    """ Get list of available classifiers for API user (via auth_token)
    """
    pipe_builder = get_pipeline_builder()

    data = []
    for opt in pipe_builder.get_classifier_options():
        doc = {'classifier_opt': opt['index'], 'label': opt['label']}
        data.append(doc)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_reductor_list(request, user, params):
    """ Get list of available reductors for API user (via auth_token)
    """
    pipe_builder = get_pipeline_builder()

    data = []
    for opt in pipe_builder.get_reductor_options():
        doc = {'reductor_opt': opt['index'], 'label': opt['label']}
        data.append(doc)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_extractor_list(request, user, params):
    """ Get list of available extractor for API user (via auth_token)
    """
    pipe_builder = get_pipeline_builder()

    data = []
    for opt in pipe_builder.get_extractor_options():
        doc = {'extractor_opt': opt['index'], 'label': opt['label']}
        data.append(doc)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_tag_list(request, user, params):
    """ Get list of available tags for API user (via auth_token)
    """
    dataset_id = params['dataset']

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)

    # Check if dataset_id is valid
    if not ds.is_active():
            error = {'error': 'invalid dataset parameter'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')

    es_m = ds.build_manager(ES_Manager)
    mass_helper = MassHelper(es_m)
    tag_set = mass_helper.get_unique_tags()
    tag_frequency = mass_helper.get_tag_frequency(tag_set)
    tag_models = set([tagger.description for tagger in Task.objects.filter(task_type='train_tagger')])

    data = []
    for tag in sorted(tag_frequency.keys()):
        count = tag_frequency[tag]
        has_model = tag in tag_models
        doc = {'description': tag,
               'count': count,
               'has_model': has_model}
        data.append(doc)
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_field_list(request, user, params):
    """ Get list of available fields for API user (via auth_token)
    """
    dataset_id = params['dataset']
    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)

    # Check if dataset_id is valid
    if not ds.is_active():
            error = {'error': 'invalid dataset parameter'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')

    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)
    data = sorted([x['path'] for x in fields])
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_mass_train_tagger(request, user, params):

    # Read all params
    dataset_id = params.get('dataset', None)
    selected_tags = set(params.get('tags', []))
    field = params.get("field", None)
    normalizer_opt = params.get("normalizer_opt", "0")
    classifier_opt = params.get("classifier_opt", "0")
    reductor_opt = params.get("reductor_opt", "0")
    extractor_opt = params.get("extractor_opt", "0")
    retrain_only = params.get("retrain_only", False)

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)
    # Check if dataset_id is valid
    if not ds.is_active():
            error = {'error': 'invalid dataset parameter'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')

    es_m = ds.build_manager(ES_Manager)
    mass_helper = MassHelper(es_m)
    
    data = mass_helper.schedule_tasks(selected_tags, normalizer_opt, classifier_opt, reductor_opt, extractor_opt, field, dataset_id, user)
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_tag_text(request, user, params):
    """ Apply tag to text (via auth_token)
    """
    text = params.get('text', "").strip()
    explain = params.get('explain', False)

    if len(text) == 0:
        error = {'error': 'text parameter cannot be empty'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    tagger_ids_list = [tagger.id for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]

    data = {'tags': [], 'explain': []}

    for tagger_id in tagger_ids_list:
        tagger = TagModelWorker()
        tagger.load(tagger_id)
        p = int(tagger.model.predict([text])[0])
        if explain:
            data['explain'].append({'tag': tagger.description, 'selected': p})
        if p == 1:
            data['tags'].append(tagger.description)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')
