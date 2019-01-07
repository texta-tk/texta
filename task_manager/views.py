import os
import json
import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from task_manager.models import Task
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL
from texta.settings import MODELS_DIR
from texta.settings import ERROR_LOGGER
from texta.settings import PROTECTED_MEDIA

from dataset_importer.document_preprocessor import preprocessor_map

from task_manager.tasks.task_params import task_params, get_fact_names
from task_manager.tools import get_pipeline_builder
from task_manager.tools import MassHelper

from .task_manager import create_task
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

    try:
        mass_helper = MassHelper(es_m)
        tag_set = mass_helper.get_unique_tags()
    except KeyError:
        tag_set = []
        
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
        get_fact_names(es_m)
        context = {
            'task_params':           task_params,
            'tasks':                 tasks,
            'language_models':       language_models,
            'allowed_datasets':      datasets,
            'searches':              Search.objects.filter(datasets__in=[Dataset.objects.get(pk=ads.id).id for ads in ds.active_datasets]).distinct(),
            'enabled_preprocessors': enabled_preprocessors,
            'STATIC_URL':            STATIC_URL,
            'fields':                fields,
            'text_tags':             sorted(tag_set)
        }
    else:
        messages.warning(request, "No dataset selected, please select a dataset before using Task Manager!")
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
    task_params = request.POST.dict()
    description = task_params['description']
    if 'dataset' in request.session.keys():
        task_params['dataset'] = request.session['dataset']

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

    if task.status == Task.STATUS_RUNNING:
        # If task is running, mark it to cancel
        task.status = Task.STATUS_CANCELED
        task.save()
    else:
        if 'train' in task.task_type:
            try:
                file_path = os.path.join(MODELS_DIR, "model_" + str(task_id))
                if (os.path.exists(file_path)):
                    os.remove(file_path)
            except Exception as e:
                file_path = os.path.join(MODELS_DIR, "model_" + str(task_id))
                logging.getLogger(ERROR_LOGGER).error('Could not delete model ({}).'.format(file_path), exc_info=True)
        if 'entity_extractor' in task.task_type or 'train_tagger' in task.task_type :
            try:
                plot_path = os.path.join(PROTECTED_MEDIA, "task_manager/model_{}_cm.svg".format(task_id))
                meta_path = os.path.join(MODELS_DIR, "model_" + str(task_id) + "_meta")
                
                if (os.path.exists(plot_path)):
                    os.remove(plot_path)
                if os.path.exists(meta_path):
                    os.remove(meta_path)
            except Exception as e:
                plot_path = os.path.join(PROTECTED_MEDIA, "task_manager/model_{}_cm.svg".format(task_id))
                facts_path = os.path.join(MODELS_DIR, "model_" + str(task_id) + "_meta")
                logging.getLogger(ERROR_LOGGER).error('Could not delete Extractor/Tagger model meta ({}) or plot ({}).'.format(facts_path, plot_path), exc_info=True)
        # Remove task
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
