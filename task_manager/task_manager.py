import json
from datetime import datetime
from django.http import QueryDict
from django.contrib.auth.models import User
from texta.settings import URL_PREFIX
from task_manager.models import Task
from utils.datasets import Datasets
from task_manager.tools import get_pipeline_builder
from lexicon_miner.models import Lexicon


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
    import pdb;pdb.set_trace()
    
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
            param_name = param[len(prefix) + 1:]
            if param_name == 'fields':
                param_val = post.getlist(param)
            else:
                param_val = post[param]
            filtered_params[param_name] = param_val
            
    if 'description' not in filtered_params:
        filtered_params['description'] = ''

    return filtered_params


def filter_preprocessor_params(post, filtered_params):
    prefix = post['apply_preprocessor_preprocessor_key']

    for param in post:
        if param.startswith(prefix):
            filtered_params[param] = post.getlist(param)

    return filtered_params


def translate_param(translation, value):
    if translation['type'] == 'url':
        return translation['pattern'].format(value)
    elif translation['type'] == 'dict':
        try:
            return translation['pattern'][int(value)]
        except KeyError:
            return '{0}: Error parsing task parameters.'.format(value)
    elif translation['type'] == 'list':
        return [translation['pattern'][int(list_item)] for list_item in value if int(list_item) in translation['pattern']]


def translate_parameters(params):
    pipe_builder = get_pipeline_builder()

    datasets = Datasets().datasets

    all_taggers = Task.objects.filter(task_type="train_tagger", status=Task.STATUS_COMPLETED)
    enabled_taggers = {tagger.pk: tagger.description for tagger in all_taggers}

    all_extraction_models = Task.objects.filter(task_type="train_entity_extractor", status=Task.STATUS_COMPLETED)
    enabled_extractors = {model.pk: model.description for model in all_extraction_models}

    extractor_options = {a['index']: a['label'] for a in pipe_builder.get_extractor_options()}
    reductor_options = {a['index']: a['label'] for a in pipe_builder.get_reductor_options()}
    normalizer_options = {a['index']: a['label'] for a in pipe_builder.get_normalizer_options()}
    classifier_options = {a['index']: a['label'] for a in pipe_builder.get_classifier_options()}

    translations = {'search': {'type': 'url', 'pattern': '<a href="' + URL_PREFIX + '/searcher?search={0}" target="_blank">{0}</a>'},
                    'extractor_opt': {'type': 'dict', 'pattern': extractor_options},
                    'reductor_opt': {'type': 'dict', 'pattern': reductor_options},
                    'normalizer_opt': {'type': 'dict', 'pattern': normalizer_options},
                    'classifier_opt': {'type': 'dict', 'pattern': classifier_options},
                    'dataset': {'type': 'list', 'pattern': datasets},
                    'text_tagger_taggers': {'type': 'list', 'pattern': enabled_taggers},
                    'entity_extractor_extractors': {'type': 'list', 'pattern': enabled_extractors}}

    params = json.loads(params)

    for k, v in params.items():
        if k in translations:
            params[k] = translate_param(translations[k], v)

    return params


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        if key == 'text_tagger':
            value['enabled_taggers'] = Task.objects.filter(task_type="train_tagger", status=Task.STATUS_COMPLETED)
        if key == 'entity_extractor':
            value['enabled_extractors'] = Task.objects.filter(task_type="train_entity_extractor", status=Task.STATUS_COMPLETED)
        if (key == 'lexicon_classifier' or key == 'scoro'):
            value['enabled_lexicons'] = Lexicon.objects.all()
        value['key'] = key
        entries.append(value)
    return entries


def get_fields(es_m):
    """ Create field list from fields in the Elasticsearch mapping
    """
    illegal_paths = ['texta_facts']
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for field_data in mapped_fields.keys():
        field_data = json.loads(field_data)
        path = field_data['path']
        if path not in illegal_paths:
            path_list = path.split('.')
            label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
            label = label.replace('-->', u'→')
            field = {'data': json.dumps(field_data), 'label': label, 'path': path}
            fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])
    return fields
