# -*- coding: utf8 -*-

import json
import logging
import requests
from multiprocessing import Process
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from searcher.models import Search
from lm.views import model_manager as lm_model_manager
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import STATIC_URL, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER

from classification_manager.models import ModelClassification
from classification_manager.models import JobQueue

from classification_manager import model_pipeline
from classification_manager.data_manager import get_fields



@login_required
def index(request):

    context = {}
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)
    context['searches'] = Search.objects.filter(author=request.user,
                                                dataset=Dataset(pk=int(request.session['dataset'])))
    context['STATIC_URL'] = STATIC_URL


    model_runs = ModelClassification.objects.all().order_by('-pk')
    model_runs_dicts = []

    for model_run in model_runs:
        model_run_dict = model_run.__dict__
        model_run_dict['train_summary_json'] = model_run_dict['train_summary']
        try:
            model_run_dict['train_summary'] = json.loads(model_run_dict['train_summary_json'])
        except ValueError:
            pass
        model_run_dict['user'] = model_run.user.username
        model_runs_dicts.append(model_run_dict)

    context['model_runs'] = model_runs_dicts




    context['fields'] = fields

    context['tagging_runs'] = JobQueue.objects.all()

    pipe_builder = model_pipeline.get_pipeline_builder()
    context['extractor_opt_list'] = pipe_builder.get_extractor_options()
    context['reductor_opt_list'] = pipe_builder.get_reductor_options()
    context['normalizer_opt_list'] = pipe_builder.get_normalizer_options()
    context['classifier_opt_list'] = pipe_builder.get_classifier_options()

    template = loader.get_template('classification_manager.html')
    return HttpResponse(template.render(context, request))


@login_required
def delete_model(request):
    model_id = request.GET['model_id']
    run = ModelClassification.objects.get(pk=model_id)
    if run.user == request.user or request.user.is_superuser:
        lm_model_manager.remove_model(run.pk)
        run.delete()
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DELETE CLASSIFIER','event':'model_deleted','args':{'user_name':request.user.username,'model_id':model_id}}))
    else:
        logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'DELETE CLASSIFIER','event':'model_deletion_failed','args':{'user_name':request.user.username,'model_id':model_id},'reason':"Created by someone else."}))
        
    return HttpResponseRedirect(URL_PREFIX + '/classification_manager')


@login_required
def start_training_job(request):

    search_id = int(request.POST['search'])
    mapped_field = request.POST['field']
    mapped_field = json.loads(mapped_field)
    field_path = mapped_field['path']
    extractor_opt = int(request.POST['extractor_opt'])
    reductor_opt = int(request.POST['reductor_opt'])
    normalizer_opt = int(request.POST['normalizer_opt'])
    classifier_opt = int(request.POST['classifier_opt'])
    tag_label = request.POST['tag_label']
    description = request.POST['description']

    usr = request.user

    clf_args = (request, usr, search_id, field_path, extractor_opt, reductor_opt,
                normalizer_opt, classifier_opt, description, tag_label)

    clf_job = Process(target=model_pipeline.train_classifier, args=clf_args)
    clf_job.start()

    return HttpResponse()


@login_required
def apply_model(request):
    post = request.POST

    model_id = post['model_id']
    model_key = post['model_key']
    search_id = post['search']

    url = '{0}/classification_manager/api/classify?model_id={1}&key={2}&search_id={3}'.format(URL_PREFIX,model_id,model_key,search_id)

    print requests.get(url).json()

    return HttpResponse()


def api_list_models(request):
    data = []

    models = ModelClassification.objects.all()

    for m in models:
        model = {}
        model['model_id'] = m.pk
        model['score'] = m.score
        model['tag_label'] = m.tag_label
        model['fields'] = m.fields
        model['architecture'] = m.clf_arch
        model['task_status'] = m.run_status
        data.append(model)

        model['searches'] = []
        searches = Search.objects.all()
        for s in searches:
            if str(m.dataset_pk) == str(s.dataset.pk):
                model['searches'].append({'search_id': s.pk,
                                          'description': s.description})

    return HttpResponse(json.dumps(data), content_type="application/json")


def api_classify(request):

    data = {}

    try:
        req = request.GET
        model_id = req['model_id']
        search_id = req['search_id']
        model_key = req['key']

        model = ModelClassification.objects.get(pk=model_id)
        dataset = Dataset.objects.get(pk=model.dataset_pk)
        search = Search.objects.get(pk=search_id)

        if model.model_key != model_key:
            data['status'] = ['failed', 'invalid model key']
        else:

            job_key = JobQueue.get_random_key()
            job_queue = JobQueue(job_key=job_key,
                                 run_status='running',
                                 run_started=datetime.now(),
                                 model=model,
                                 dataset=dataset,
                                 search=search,
                                 run_completed=None,
                                 total_processed='--',
                                 total_positive='--',
                                 total_negative='--',
                                 total_documents='--')
            job_queue.save()
            data['status'] = ['running', 'model added to job queue']
            data['job_key'] = job_key
            model_job = Process(target=model_pipeline.apply_classifier, args=(job_key,))
            model_job.start()

    except Exception as e:
        print 'Error: ', e
        data['status'] = ['failed', 'exception']
    return HttpResponse(json.dumps(data), content_type="application/json")


def api_job_status(request):
    data = {}
    try:
        req = request.GET
        job_key = req['job_key']
        job_queue = JobQueue.objects.get(job_key=job_key)
        model = ModelClassification.objects.get(pk=job_queue.model_id)
        dataset = Dataset.objects.get(pk=job_queue.dataset_id)

        # Load model info
        data['model_info'] = {}
        data['model_info']['model_id'] =model.pk
        data['model_info']['training_score'] = model.score
        data['model_info']['tag_label'] = model.tag_label
        data['model_info']['task_status'] = model.run_status
        data['model_info']['dataset_pk'] = model.dataset_pk
        data['dataset_info'] = {}
        data['dataset_info']['index'] = dataset.index
        data['dataset_info']['mapping'] = dataset.mapping
        data['dataset_info']['daterange'] = dataset.daterange
        data['dataset_info']['author'] = dataset.author.username
        data['job'] = {}
        data['job']['status'] = job_queue.run_status
        data['job']['started'] = str(job_queue.run_started)
        data['job']['ended'] = str(job_queue.run_completed)
        data['job']['total_processed'] = job_queue.total_processed
        data['job']['total_positive'] = job_queue.total_positive
        data['job']['total_negative'] = job_queue.total_negative
        data['job']['total_documents'] = job_queue.total_documents

    except Exception as e:
        print 'Error: ', e
        data['status'] = ['failed', 'exception']
    return HttpResponse(json.dumps(data), content_type="application/json")


def api_jobs(request):
    data = {}
    try:
        status_count = {}
        jobs = JobQueue.objects.all()
        for j in jobs:
            s = j.run_status
            if s not in status_count:
                status_count[s] = 0
            status_count[s] += 1

        data['jobs'] = {}
        for k in status_count:
            data['jobs'][k] = status_count[k]

    except Exception as e:
        print '- Expcetion: ', e
    return HttpResponse(json.dumps(data), content_type="application/json")
