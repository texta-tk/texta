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
from task_manager.models import TagFeedback


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
def api_tagger_list(request, user, params):
    """ Get list of available tagger for API user (via auth_token)
    """
    all_taggers = Task.objects.filter(task_type="train_tagger", status=Task.STATUS_COMPLETED)
    data = []
    for tagger in all_taggers:
        doc = {'tagger': tagger.id, 'description': tagger.description}
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
def api_mass_tagger(request, user, params):

    # Fix Default Params
    if 'search' not in params:
        params['search'] = 'all_docs'
    if 'description' not in params:
        params['description'] = "via API call"
    
    task_type = "apply_preprocessor"
    params["preprocessor_key"] = "text_tagger"
    params["text_tagger_feature_names"] = params['field']
    
    taggers = params.get('taggers', None)
    if taggers is None:
        taggers = [tagger.id for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]
    params['text_tagger_taggers'] = taggers

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
def api_tag_text(request, user, params):
    """ Apply tag to text (via auth_token)
    """
    text = params.get('text', "").strip()
    explain = params.get('explain', False)
    taggers = params.get('taggers', None)

    if len(text) == 0:
        error = {'error': 'text parameter cannot be empty'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    tagger_ids_list = [tagger.id for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]

    data = {'tags': [], 'explain': []}

    for tagger_id in tagger_ids_list:
        is_tagger_selected = taggers is None or tagger_id in taggers
        tagger = TagModelWorker()
        tagger.load(tagger_id)
        p = int(tagger.model.predict([text])[0])
        if explain:
            data['explain'].append({'tag': tagger.description, 
                                    'prediction': p,
                                    'selected': is_tagger_selected })
        if p == 1 and is_tagger_selected:
            data['tags'].append(tagger.description)

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@api_auth
def api_tag_feedback(request, user, params):
    """ Apply tag feedback (via auth_token)
    """
    dataset_id = params.get('dataset', None)
    document_ids = params.get('document_ids', None)
    tag = params.get('tag', None)
    field = params.get('field', None)
    value = int(params.get('value', 1))

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)
    # Check if dataset_id is valid
    if not ds.is_active():
        error = {'error': 'invalid dataset parameter'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    es_m = ds.build_manager(ES_Manager)
    mass_helper = MassHelper(es_m)
    resp = mass_helper.get_document_by_ids(document_ids)

    docs_to_update = []

    for hit in resp['hits']['hits']:
        doc = hit['_source']
        if value == 1:
            doc = _add_tag_to_document(doc, field, tag)
        else:
            doc = _remove_tag_from_document(doc, field, tag)
        docs_to_update.append(doc)
    
    es_m.update_documents(docs_to_update, document_ids)
    data = []
    for doc_id in document_ids:
        tag_feedback = TagFeedback.log(user, dataset_id, doc_id, field, tag, value)
        data.append(tag_feedback.to_json())
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


def _add_tag_to_document(doc, field, tag):
    decoded_text = doc
    for k in field.split('.'):
        # Field might be empty and not included in document
        if k in decoded_text:
            decoded_text = decoded_text[k]
        else:
            decoded_text = ''
            break
    if 'texta_facts' not in doc:
        doc['texta_facts'] = []

    new_fact = {
        'fact': 'TEXTA_TAG',
        'str_val': tag,
        'doc_path': field,
        'spans': json.dumps([[0, len(decoded_text)]])
    }
    doc['texta_facts'].append(new_fact)
    return doc


def _remove_tag_from_document(doc, field, tag):
    
    if 'texta_facts' not in doc:
        # Nothing to remove
        return doc

    filtered_facts = []
    for fact in doc['texta_facts']:
        cond_1 = fact['fact'] == 'TEXTA_TAG'
        cond_2 = fact['str_val'] == tag
        cond_3 = fact['doc_path'] == field
        if cond_1 and cond_2 and cond_3:
            # Conditions to remove fact was met
            continue
        filtered_facts.append(fact)
    # Replace facts 
    doc['texta_facts'] = filtered_facts
    return doc


@api_auth
def api_document_tags_list(request, user, params):
    """ Get document tags (via auth_token)
    """
    dataset_id = params.get('dataset', None)
    document_ids = params.get('document_ids', None)

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)
    # Check if dataset_id is valid
    if not ds.is_active():
        error = {'error': 'invalid dataset parameter'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    es_m = ds.build_manager(ES_Manager)
    mass_helper = MassHelper(es_m)
    resp = mass_helper.get_document_by_ids(document_ids)

    data = []
    for doc in resp['hits']['hits']:
        for f in doc['_source'].get('texta_facts', []):
            if f['fact'] == 'TEXTA_TAG':
                doc_id = doc['_id']
                doc_path = f['doc_path']
                doc_tag = f['str_val']
                data.append({ 'document_id': doc_id, 'field': doc_path, 'tag': doc_tag})

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')
