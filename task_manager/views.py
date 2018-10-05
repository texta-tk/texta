
import os
import json
import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.contrib.auth.decorators import login_required
from task_manager.models import Task
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL
from texta.settings import MODELS_DIR
from texta.settings import ERROR_LOGGER

from dataset_importer.document_preprocessor import preprocessor_map
# from .language_model_manager.language_model_manager import LanguageModel
# from .tag_manager.tag_manager import TaggingModel, get_pipeline_builder
# from task_manager.tasks import Preprocessor
# from .models import Task

from task_manager.tasks.task_params import task_params
from task_manager.tools import get_pipeline_builder
from task_manager.tools import MassHelper

from .task_manager import create_task
from .task_manager import filter_params
from .task_manager import filter_preprocessor_params
from .task_manager import translate_parameters
from .task_manager import collect_map_entries
from .task_manager import get_fields


@login_required
def index(request):
    ds = Datasets().activate_datasets(request.session)
    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status__iexact='completed').order_by('-pk')

    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)

    mass_helper = MassHelper(es_m)
    tag_set = mass_helper.get_unique_tags()

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

    text_tags = [str(x) for x in range(100)]

    if 'dataset' in request.session.keys():
        context = {
            'task_params':           task_params,
            'tasks':                 tasks,
            'language_models':       language_models,
            'allowed_datasets':      datasets,
            'searches':              Search.objects.filter(pk__in=[Dataset.objects.get(pk=ads.id).id for ads in ds.active_datasets]),
            'enabled_preprocessors': enabled_preprocessors,
            'STATIC_URL':            STATIC_URL,
            'fields':                fields,
            'text_tags':             sorted(tag_set)
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
def start_mass_task(request):
    
    user = request.user
    data_post = request.POST

    selected_tags = set(data_post.getlist('mass_tagger_selection'))
    field = data_post.get('mass_field')
    extractor_opt = data_post.get('mass_extractor_opt')
    reductor_opt = data_post.get('mass_reductor_opt')
    normalizer_opt = data_post.get('mass_normalizer_opt')
    classifier_opt = data_post.get('mass_classifier_opt')

    ds = Datasets().activate_dataset(request.session)
    dataset_id = ds.mapping_id
    es_m = ds.build_manager(ES_Manager)
    mass_helper = MassHelper(es_m)
    data = mass_helper.schedule_tasks(selected_tags, normalizer_opt, classifier_opt, reductor_opt, extractor_opt, field, dataset_id, user)
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
