import os
import json
import logging
import zipfile
from zipfile import ZipFile
from tempfile import SpooledTemporaryFile
from django.core import serializers
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from task_manager.models import Task
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.helper_functions import get_wildcard_files, create_file_path
from texta.settings import STATIC_URL
from texta.settings import MODELS_DIR
from texta.settings import PROTECTED_MEDIA
from texta.settings import ERROR_LOGGER

from task_manager.document_preprocessor import preprocessor_map

from task_manager.tasks.task_params import task_params, get_fact_names, fact_names
from task_manager.tools import get_pipeline_builder
from task_manager.tools import MassHelper
from task_manager.tasks.task_types import TaskTypes

from task_manager.task_manager import filter_params
from task_manager.task_manager import create_task
from task_manager.task_manager import filter_preprocessor_params
from task_manager.task_manager import translate_parameters
from task_manager.task_manager import collect_map_entries
from task_manager.task_manager import get_fields
from operator import itemgetter

@login_required
def index(request):
    ds = Datasets().activate_datasets(request.session)
    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL).filter(status__iexact='completed').order_by('-pk')

    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)
        
    preprocessors = collect_map_entries(preprocessor_map)
    enabled_preprocessors = [preprocessor for preprocessor in preprocessors if preprocessor['is_enabled'] is True]
    enabled_preprocessors = sorted(enabled_preprocessors, key=itemgetter('name'), reverse=False)
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
        tag_set = fact_names if fact_names else []

        context = {
            'task_params':           task_params,
            'tasks':                 tasks,
            'language_models':       language_models,
            'allowed_datasets':      datasets,
            'searches':              Search.objects.filter(datasets__in=[Dataset.objects.get(pk=ads.id).id for ads in ds.active_datasets]).distinct(),
            'enabled_preprocessors': enabled_preprocessors,
            'STATIC_URL':            STATIC_URL,
            'fields':                fields,
            'text_tags':             tag_set
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
    task_type = TaskTypes(request.POST['task_type'])
    print(task_type)
    print(type(task_type))
    task_params = filter_params(request.POST)

    description = task_params['description']
    if 'dataset' in request.session.keys():
        task_params['dataset'] = request.session['dataset']

    if 'model' in request.session.keys():
        task_params['language_model'] = request.session['model']

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
    task_ids = request.POST.getlist('task_ids[]')

    for task_id in task_ids:
        task_id = int(task_id)
        task = Task.objects.get(pk=task_id)

        if task.status == Task.STATUS_RUNNING:
            # If task is running, mark it to cancel
            task.status = Task.STATUS_CANCELED
            task.save()
        else:
            try:
                file_path = os.path.join(MODELS_DIR, task.task_type, "model_{}".format(task.unique_id))
                media_path = os.path.join(PROTECTED_MEDIA, "task_manager/", task.task_type, "model_{}".format(task.unique_id))

                model_files = get_wildcard_files(file_path)
                media_files = get_wildcard_files(media_path)

                for path, filename in model_files:
                    if os.path.exists(path):
                        os.remove(path)

                for path, filename in media_files:
                    if os.path.exists(path):
                        os.remove(path)

            except Exception as e:
                logging.getLogger(ERROR_LOGGER).error('Could not delete model, paths: ({}\n{}).'.format(model_files, media_files), exc_info=True)
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

    if 'model_id' in request.GET:
        model_id = request.GET['model_id']
        task_object = Task.objects.get(pk=model_id)
        if task_object.status == "completed":
            unique_id = task_object.unique_id
            task_type = task_object.task_type

            task_xml_name = "task_{}.xml".format(unique_id)
            model_name = "model_{}".format(unique_id)

            model_file_path = os.path.join(MODELS_DIR, task_type, model_name)
            media_path = os.path.join(PROTECTED_MEDIA, "task_manager/", task_type, model_name)

            model_files = get_wildcard_files(model_file_path)
            media_files = get_wildcard_files(media_path)

            zip_path = "zipped_model_{}.zip".format(model_id)
            # Make temporary Zip file
            with SpooledTemporaryFile() as tmp:
                with ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                    # Write Task model object as xml
                    task_xml_data = serializers.serialize("xml", [task_object])
                    archive.writestr(task_xml_name, task_xml_data)
                    # Write model files
                    for path, name in model_files:
                        archive.write(path, "model/"+name)

                    for path, name in media_files:
                        archive.write(path, "media/"+name)

                # Reset file pointer
                tmp.seek(0)
                # Write file data to response
                response = HttpResponse(tmp.read())
                # Download file
                response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_path)

                return response

    return HttpResponse()

@login_required
def upload_task_archive(request):
    # Empty json response for unknown errors
    json_response = {}
    try:
        # Check if file is added, else return failed JsonResponse
        if 'task_archive' in request.FILES:
            task_archive = request.FILES['task_archive']
            # Check if file is zipfile, else return failed JsonResponse
            if zipfile.is_zipfile(task_archive):
                task_loaded = False
                with ZipFile(task_archive, 'r') as zf:
                    for file_name in zf.namelist():
                        dirname = os.path.dirname(file_name)
                        # Handle Task object xml
                        if dirname == '' and file_name.lower().endswith('.xml'):
                            task = _load_xml_to_database(zf.read(file_name))
                            task_loaded = True
                        # Check if task is loaded else return failed JsonResponse
                        if task_loaded:
                            if dirname == 'model':
                                _load_model_file(task, zf.read(file_name), os.path.basename(file_name))
                                model_loaded = True
                            elif dirname == 'media':
                                _load_media_file(task, zf.read(file_name), os.path.basename(file_name))

                # Give successful response if task and model were loaded
                if task_loaded and model_loaded:
                    json_response = {"status": "success", "text": "Task successfully uploaded!"}   
                else: 
                    json_response = {"status": "failed", "text": "Archive seems to not contain a valid model or Task object"}
            # If file is not zipfile
            else:
                json_response = {"status": "failed", "text": "Archive contents malformed or not a .zip file"}
                return JsonResponse(json_response)
        # If there is no file found in request.FILES
        else:
            json_response = {"status": "failed", "text": "No file provided"}
    except:
        logging.getLogger(ERROR_LOGGER).error(
            'Exception in Task Manager views:upload_task_archive',
            exc_info=True
        )

    return JsonResponse(json_response)


def _load_xml_to_database(xml_model_object):
    task = None
    # Decode bytes object
    xml_model_object = xml_model_object.decode('utf8')
    for task in serializers.deserialize("xml", xml_model_object):
        # Save object to model dataset
        task.save()
    # Return the Task obj from the Deserialized object
    return task.object


def _load_model_file(task, file, file_name):
    '''For extracting the uploaded model in upload_task_archive'''
    model_file_path = create_file_path(file_name, MODELS_DIR, task.task_type)#os.path.join(MODELS_DIR, task.task_type, file_name)

    with open(model_file_path, 'wb+') as f:
        f.write(file)


def _load_media_file(task, file, file_name):
    '''For extracting the uploaded model mediadata in upload_task_archive'''
    # media_file_path = os.path.join(PROTECTED_MEDIA, "task_manager/", task.task_type, file_name)
    media_file_path = create_file_path(file_name, PROTECTED_MEDIA, "task_manager/", task.task_type)
    
    with open(media_file_path, 'wb+') as f:
        f.write(file)
