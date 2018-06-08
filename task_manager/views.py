from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from task_manager.models import Task
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL, URL_PREFIX

from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map
from .language_model_manager.language_model_manager import LanguageModel
from .tag_manager.tag_manager import TaggingModel, get_pipeline_builder

from datetime import datetime

import json

task_params = [{"name": "Train Language Model", "id": "train_model", "template": "task_parameters/train_model.html", "model": LanguageModel()},
               {"name": "Train Text Tagger", "id": "train_tagger", "template": "task_parameters/train_tagger.html", "model": TaggingModel()},
              {"name": "Apply preprocessor", "id": "apply_preprocessor", "template": "task_parameters/apply_preprocessor.html"},
              #{"name": "Apply text tagger", "id": "apply_tagger", "template": "task_parameters/apply_tagger.html"},
              ]

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
            field = {'data': json.dumps(data), 'label': label}
            fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)

    return entries


@login_required
def index(request):
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)

    preprocessors = collect_map_entries(preprocessor_map)
    enabled_preprocessors = [preprocessor for preprocessor in preprocessors]

    context = {'task_params': task_params,
               'tasks': Task.objects.all().order_by('-pk'),
               'searches': Search.objects.filter(author=request.user,dataset=Dataset(pk=int(request.session['dataset']))),
               'enabled_preprocessors': enabled_preprocessors,
               'STATIC_URL': STATIC_URL,
               'fields': fields}
    
    
    pipe_builder = get_pipeline_builder()
    context['train_tagger_extractor_opt_list'] = pipe_builder.get_extractor_options()
    context['train_tagger_reductor_opt_list'] = pipe_builder.get_reductor_options()
    context['train_tagger_normalizer_opt_list'] = pipe_builder.get_normalizer_options()
    context['train_tagger_classifier_opt_list'] = pipe_builder.get_classifier_options()

    template = loader.get_template('task_manager.html')
    return HttpResponse(template.render(context, request))


@login_required
def start_task(request):
    user = request.user
    session = request.session
    task_params = request.POST

    task_type = task_params['task_type']
    task_params = filter_params(task_params, task_type)   
    description = task_params['description']

    if 'dataset' in request.session.keys():
        task_params['dataset'] = int(request.session['dataset'])

    task_id = create_task(task_type, description, task_params, user)
    
    
    model = activate_model(task_type)
    model.train(task_id)

    return HttpResponseRedirect('{0}/task_manager'.format(URL_PREFIX))


def activate_model(task_type):
    for task_param in task_params:
        if task_param['id'] == task_type:
            return task_param['model']
    return None


def create_task(task_type, description, parameters, user):
    # Creates a db entry for new task and returns task ID
    new_task = Task(description = description,
                    task_type = task_type,
                    parameters = json.dumps(parameters),
                    status = 'running',
                    time_started = datetime.now(),
                    time_completed = None,
                    result = '',
                    user = user)
    new_task.save()
    return new_task.pk


def filter_params(params, prefix):
    filtered_params = {}
    for param in params:
        if param.startswith(prefix):
            filtered_params[param[len(prefix)+1:]] = params[param]
    return filtered_params

