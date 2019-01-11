import json
import uuid
from task_manager.models import Task, TagFeedback
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from account.api_auth import api_auth
import pandas as pd

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

from dataset_importer.document_preprocessor import preprocessor_map
from dataset_importer.document_preprocessor import PREPROCESSOR_INSTANCES

API_VERSION = "1.0"


def api_info(request):
    """ Get basic API info
    """
    data = {'name': 'TEXTA Task Manager API',
            'version': API_VERSION}
    data_json = json.dumps(data)
    return HttpResponse(data_json, content_type='application/json')


@csrf_exempt
@api_auth
def api_get_task_list(request, user, params):
    """ Get list of tasks
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


@csrf_exempt
@api_auth
def api_get_task_status(request, user, params):
    """ Get task status for a given task id
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


@csrf_exempt
@api_auth
def api_train_model(request, user, params):
    """ Create task for train model
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


@csrf_exempt
@api_auth
def api_train_tagger(request, user, params):
    """ Create task for train tagger
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


@csrf_exempt
@api_auth
def api_apply(request, user, params):
    """ Create task for apply processor
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


@csrf_exempt
@api_auth
def api_apply_text(request, user, params):
    """ Apply preprocessor to input document
    """
    preprocessor_key = params["preprocessor_key"]
    preprocessor_params = params["parameters"]
    documents = params["documents"]

    preprocessor = PREPROCESSOR_INSTANCES[preprocessor_key]
    
    try:
        result_map = preprocessor.transform(documents, **preprocessor_params)
    except Exception as e:
        result_map = {"error": "preprocessor internal error: {}".format(repr(e))}
    data_json = json.dumps(result_map)
    return HttpResponse(data_json, status=200, content_type='application/json')


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
@api_auth
def api_tagger_info(request, user, params):
    """ Get tagger info for API user (via auth_token)
    """
    tagger_id = params['tagger']
    tagger = list(Task.objects.filter(task_type="train_tagger", id=tagger_id))[0]

    model_worker = TagModelWorker()
    model = model_worker.load(tagger_id)
    # Get model fields
    if 'union' in model.named_steps:
        union_features = [x[0] for x in model.named_steps['union'].transformer_list if x[0].startswith('pipe_')]
        field_features = [x[5:] for x in union_features]
        data = {'tagger': tagger.id, 
                'fields': field_features,
                'tag': tagger.description,
                'model_description': str(model)
                }
    else:
        data = {"error": "model does not contain union features"}

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
@api_auth
def api_mass_train_tagger(request, user, params):
    """ Apply mass train tagger (via auth_token)
    """
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


@csrf_exempt
@api_auth
def api_mass_tagger(request, user, params):
    """ Apply mass tagger (via auth_token)
    """
    # Get parameters with default values
    if 'search' not in params:
        params['search'] = 'all_docs'
    if 'description' not in params:
        params['description'] = "via API call"
    # Paramater projection for preprocessor task
    task_type = "apply_preprocessor"
    params["preprocessor_key"] = "text_tagger"
    params["text_tagger_feature_names"] = params['field']
    # Select taggers
    taggers = params.get('taggers', None)
    if taggers is None:
        taggers = [tagger.id for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]
    params['text_tagger_taggers'] = taggers
    # Prepare description
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


@csrf_exempt
@api_auth
def api_hybrid_tagger(request, user, params):
    """ Apply hybrid tagger (via auth_token)
    """
    DEFAULT_TAGS_THRESHOLD = 50
    DEFAULT_MAX_TAGGERS = 20

    dataset_id = params['dataset']
    search = params['search']
    field = params['field']
    max_taggers = int(params.get('max_taggers', DEFAULT_MAX_TAGGERS))
    min_count_threshold = int(params.get('min_count_threshold', DEFAULT_TAGS_THRESHOLD))

    if 'description' not in params:
        params['description'] = "via API call"
    # Paramater projection for preprocessor task
    task_type = "apply_preprocessor"
    params["preprocessor_key"] = "text_tagger"
    params["text_tagger_feature_names"] = params['field']

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)
    # Check if dataset_id is valid
    if not ds.is_active():
        error = {'error': 'invalid dataset parameter'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    param_query = json.loads(Search.objects.get(pk=int(search)).query)
    es_m = ds.build_manager(ES_Manager)    
    es_m.load_combined_query(param_query)
    # Get similar documents in a neighborhood of size 1000
    response = es_m.more_like_this_search([field], search_size=1000)
    docs = response['hits']['hits']
    # Build Tag frequency
    tag_freq = {}
    for doc in docs:
        for f in doc['_source'].get('texta_facts', []):
            if f['fact'] == 'TEXTA_TAG' and f['doc_path'] == field:
                doc_tag = f['str_val']
                if doc_tag not in tag_freq:
                    tag_freq[doc_tag] = 0
                tag_freq[doc_tag] += 1

    # Top Tags to limit the number of taggers
    top_tags = [t[0] for t in sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)]
    top_tags = set(top_tags[:max_taggers])
    # Perform tag selection
    data = {'task': {}, 'explain': []}
    candidate_tags = set()
    for tag in tag_freq:
        selected = 0
        count = tag_freq[tag]
        if count >= min_count_threshold and tag in top_tags:
            selected = 1
            candidate_tags.add(tag)
        data['explain'].append({'tag': tag, 
                                'selected': selected, 
                                'count': count })
    # Filter tags
    tagger_search = Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)
    taggers = [tagger.id for tagger in tagger_search if tagger.description in candidate_tags]
    # Create Task if taggers is not zero
    if len(taggers) > 0:
        description = params['description']
        params['text_tagger_taggers'] = taggers
        # Create execution task
        task_id = create_task(task_type, description, params, user)
        # Add task to queue
        task = Task.get_by_id(task_id)
        task.update_status(Task.STATUS_QUEUED)
        # Return reference to task
        data['task'] = {
            'task_id': task_id,
            'task_type': task_type,
            'status': task.status,
            'user': task.user.username
        }
    else:
        # If here, no taggers were selected
        data['task'] = {"error": "no similar documents have tags count above threshold"}
    # Generate response
    data['min_count_threshold'] = min_count_threshold
    data['max_taggers'] = max_taggers
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@csrf_exempt
@api_auth
def api_tag_text(request, user, params):
    """ Apply tag to text (via auth_token)
    """
     # Get parameters with default values
    text_dict = params.get('text', "{}")
    taggers = params.get('taggers', None)

    # Check if text input is valid
    if not text_dict:
        error = {'error': 'text parameter cannot be empty'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    # preprocess if necessary
    preprocessor = params.get('preprocessor', None)
    if preprocessor:
        preprocessor_params = {}
        preprocessor = PREPROCESSOR_INSTANCES[preprocessor]

        try:
            result_map = preprocessor.transform([text_dict], **preprocessor_params)
        except Exception as e:
            result_map = {"error": "preprocessor internal error: {}".format(repr(e))}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')

        text_dict = result_map['documents'][0]

    # Select taggers
    tagger_ids_list = [tagger.id for tagger in Task.objects.filter(task_type='train_tagger').filter(status=Task.STATUS_COMPLETED)]
    data = {'tags': [], 'explain': []}

    # Apply
    for tagger_id in tagger_ids_list:
        is_tagger_selected = taggers is None or tagger_id in taggers
        c = None
        p = 0

        if is_tagger_selected:
            tagger = TagModelWorker()
            tagger.load(tagger_id)

            explain = {'tag': tagger.description,
                       'tagger_id': tagger_id}

            # create input for the tagger
            tagger_fields = json.loads(Task.objects.get(pk = tagger_id).parameters)['fields']
            text_dict_df = {}

            for field in tagger_fields:
                sub_field_content = text_dict
                for sub_field in field.split('.'):
                    sub_field_content = sub_field_content[sub_field]

                text_dict_df[field] = [sub_field_content]

            if 'error' not in explain:
                try:
                    df_text = pd.DataFrame(text_dict_df)
                    # tag
                    p = int(tagger.model.predict(df_text)[0])
                    # get confidence
                    c = tagger.model.decision_function(df_text)[0]
                    # create (empty) feedback item
                    feedback_obj = TagFeedback.create(user, text_dict, tagger_id, p)
                    explain['decision_id'] = feedback_obj.pk
                except Exception as e:
                    explain['error'] = str(e)
            
            explain['prediction'] = p
            explain['confidence'] = c
            data['explain'].append(explain)
        
        # Add prediction as tag
        if p == 1:
            data['tags'].append(tagger.description)

    # Prepare response
    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


@csrf_exempt
@api_auth
def api_tag_feedback(request, user, params):
    """ Apply tag feedback (via auth_token)
        Currently working corrently with 1 tag per document. Needs further development.
    """
    decision_id = params.get('decision_id', None)

    if not decision_id:
        error = {'error': 'no decision ID supported'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')
    
    doc_path = params.get('doc_path', None)

    if not doc_path:
        error = {'error': 'no doc_path supported. cannot index feedback'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    prediction = params.get('prediction', None)

    if not prediction:
        error = {'error': 'no prediction supported'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')

    feedback_obj = TagFeedback.update(user, decision_id, prediction)

    # retrieve dataset id from task params
    params = Task.objects.get(pk = feedback_obj.tagger.pk).parameters
    params_json = json.loads(params)
    dataset_id = params_json['dataset']
    tagger_name = params_json['description']

    ds = Datasets()
    ds.activate_dataset_by_id(dataset_id, use_default=False)

    # Check if dataset_id is valid
    if not ds.is_active():
        error = {'error': 'invalid dataset parameter'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=400, content_type='application/json')


    document = json.loads(feedback_obj.document)
    in_dataset = int(feedback_obj.in_dataset)

    data = {'success': True}

    # check if document already indexed in ES
    if in_dataset == 0:
        es_m = ds.build_manager(ES_Manager)

        # add tag to the document
        if prediction > 0:
            # add facts here!!!!
            new_fact = {"fact": "TEXTA_TAG", "str_val": tagger_name, "doc_path": doc_path, "spans": "[[0,0]]"}
            document['texta_facts'] = [new_fact]
        
        es_m.add_document(document)

        feedback_obj.in_dataset = 1
        feedback_obj.save()
        data['feedback_indexed'] = True
    else:
        data['feedback_indexed'] = False

    data_json = json.dumps(data)
    return HttpResponse(data_json, status=200, content_type='application/json')


def _add_tag_to_document(doc, field, tag):
    """ Add tag from Texta facts field into document

    Parameters
    ----------
    doc: dict
        The elasticsearch document
    field: string
        The reference path inside the document
    tag: string
        The tag to be add in the document

    Returns
    -------
    dict
        The processed document
    """
    decoded_text = doc
    for k in field.split('.'):
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
    """ Remove tag from Texta facts field in document

    Parameters
    ----------
    doc: dict
        The elasticsearch document
    field: string
        The reference path inside the document
    tag: string
        The tag to be removed from document

    Returns
    -------
    dict
        The processed document
    """
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


@csrf_exempt
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
