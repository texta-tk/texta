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
from task_manager.tools import MassHelper
from task_manager.tools import get_pipeline_builder


MIN_DOCS_TAGGED = 100


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
    tag_models = set([tagger.description for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)])

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

    if len(selected_tags) == 0:
        selected_tags = tag_set
    else:
        # Check if all selected tag are in tag_set
        for tag in selected_tags:
            if tag not in tag_set:
                error = {'error': 'invalid tag parameter'}
                data_json = json.dumps(error)
                return HttpResponse(data_json, status=400, content_type='application/json')

    tag_frequency = mass_helper.get_tag_frequency(selected_tags)
    retrain_tasks = []
    # Get list of available models
    task_tagger_list = [tagger for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]
    task_tagger_tag_set = set([tagger.description for tagger in task_tagger_list])

    for task_tagger in task_tagger_list:

        # Get tag label
        tag_label = task_tagger.description
        # Filter models that are not included in the tag_frequency map
        if tag_label not in tag_frequency:
            continue
        # Filter models with less than MIN_DOCS_TAGGED docs
        if tag_frequency.get(tag_label, 0) < MIN_DOCS_TAGGED:
            continue
        # Filter running tasks
        if task_tagger.is_running():
            continue
        # If here, retrain model with tags (re-queue task)
        task_id = task_tagger.pk
        retrain_task = {'task_id': task_id, 'tag': tag_label}
        retrain_tasks.append(retrain_task)

        # Update query parameter from task
        tag_parameters = json.loads(task_tagger.parameters)
        _add_search_tag_query(tag_parameters, tag_label)
        task_tagger.parameters = json.dumps(tag_parameters)
        task_tagger.requeue_task()

    new_model_tasks = []
    for tag_label in selected_tags:
        # Check if it is a new model
        if tag_label in task_tagger_tag_set:
            continue
        # Filter models with less than MIN_DOCS_TAGGED docs
        if tag_frequency.get(tag_label, 0) < MIN_DOCS_TAGGED:
            continue
        # Check if field params is valid
        if field is None:
            error = {'error': 'invalid field parameter for new model'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')
        # Build task parameters
        task_param = {}
        task_param["description"] = tag_label
        task_param["normalizer_opt"] = normalizer_opt
        task_param["classifier_opt"] = classifier_opt
        task_param["reductor_opt"] = reductor_opt
        task_param["extractor_opt"] = extractor_opt
        task_param["field"] = field
        task_param["dataset"] = dataset_id
        _add_search_tag_query(task_param, tag_label)
        # Create execution task
        task_type = "train_tagger"
        task_id = create_task(task_type, tag_label, task_param, user)
        # Add task to queue
        task = Task.get_by_id(task_id)
        task.update_status(Task.STATUS_QUEUED)
        # Add task id to response
        new_model_task = {'task_id': task_id, 'tag': tag_label}
        new_model_tasks.append(new_model_task)

    data = {'retrain_models': retrain_tasks, 'new_models': new_model_tasks}
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


def _add_search_tag_query(param_dict, tag_label):
    param_dict['search_tag'] = {}
    param_dict['search_tag']['main'] = {}
    param_dict['search_tag']['main']['query'] = {}
    param_dict['search_tag']['main']['query']['nested'] = {}
    param_dict['search_tag']['main']['query']['nested']['path'] = "texta_facts"
    param_dict['search_tag']['main']['query']['nested']['query'] = {'term': {"texta_facts.str_val": tag_label}}
