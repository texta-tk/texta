# -*- coding: utf8 -*-
import json
import logging
import os
from multiprocessing import Process
from datetime import datetime
import hashlib
import random

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from corpus_tool.models import Search
from lm.views import model_manager as lm_model_manager
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import STATIC_URL, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER

import time

from classification_manager.models import ModelClassification
from classification_manager import model_pipeline
from classification_manager.data_manager import EsDataSample
from classification_manager.data_manager import EsDataClassification


def get_fields(es_m):
    """ Crete field list from fields in the Elasticsearch mapping
    """
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        path = data['path']
        path_list = path.split('.')
        label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
        label = label.replace('-->', u'→')
        field = {'data': json.dumps(data), 'label': label}
        fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields


@login_required
def index(request):

    context = {}

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)

    context['searches'] = Search.objects.filter(author=request.user,
                                                dataset=Dataset(pk=int(request.session['dataset'])))
    context['STATIC_URL'] = STATIC_URL
    context['runs'] = ModelClassification.objects.all().order_by('-pk')
    context['fields'] = fields

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

    clf_job = Process(target=train_classifier, args=clf_args)
    clf_job.start()

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

    return HttpResponse(json.dumps(data), content_type="application/json")


def api_classify(request):

    data = {}

    try:
        req = request.GET
        model_id = req['model_id']
        docs = req['docs']
        model_key = req['key']

        if docs == "all":
            docs_list = None
        else:
            docs_list = json.loads(docs)

        model = ModelClassification.objects.get(pk=model_id)

        if model.model_key != model_key:
            data['status'] = ['failed', 'invalid model key']

        else:
            # Load model info
            data['model_info'] = {}
            data['model_info']['model_id'] = model_id
            data['model_info']['training_score'] = model.score
            data['model_info']['tag_label'] = model.tag_label
            data['model_info']['task_status'] = model.run_status
            data['model_info']['dataset_pk'] = model.dataset_pk

            # Load dataset info
            model_dataset = Dataset.objects.get(pk=model.dataset_pk)
            data['dataset_info'] = {}
            data['dataset_info']['index'] = model_dataset.index
            data['dataset_info']['mapping'] = model_dataset.mapping
            data['dataset_info']['daterange'] = model_dataset.daterange
            data['dataset_info']['author'] = model_dataset.author.username

            es_index = model_dataset.index
            es_mapping = model_dataset.mapping
            es_daterange = model_dataset.daterange
            field_path = model.fields

            if model.run_status == 'completed':
                model_name = 'classifier_{0}.pkl'.format(model_id)
                output_model_file = os.path.join(MODELS_DIR, model_name)
                clf_model = model_pipeline.load_model(output_model_file)
                es_classification = EsDataClassification(es_index, es_mapping, es_daterange, field_path)
                _data = es_classification.apply_classifier(clf_model, model.tag_label, filter_ids=docs_list)
                data.update(_data)
                data['status'] = ['ok', 'classification completed']
            else:
                data['status'] = ['failed', 'model has invalid status']

    except Exception as e:
        print 'Error: ', e
        data['status'] = ['failed', 'exception']

    return HttpResponse(json.dumps(data), content_type="application/json")


# Ref: http://stackoverflow.com/questions/26646362/numpy-array-is-not-json-serializable
def jsonify(data):
    json_data = dict()
    for key, value in data.iteritems():
        if isinstance(value, list):
            value = [ jsonify(item) if isinstance(item, dict) else item for item in value ]
        if isinstance(value, dict):
            value = jsonify(value)
        if isinstance(key, int):
            key = str(key)
        if type(value).__module__=='numpy':
            value = value.tolist()
        json_data[key] = value
    return json_data


def train_classifier(request, usr, search_id, field_path, extractor_opt, reductor_opt,
                     normalizer_opt, classifier_opt, description, tag_label):

    # add Run to db
    dataset_pk = int(request.session['dataset'])
    model_status = 'running'
    model_score = "---"
    clf_arch = "---"
    train_summary = "---"

    key_str = '{0}-{1}'.format(dataset_pk, random.random() * 100000)
    model_key = hashlib.md5(key_str).hexdigest()

    new_run = ModelClassification(run_description=description, tag_label=tag_label, fields=field_path,
                                  score=model_score, search=Search.objects.get(pk=search_id).query,
                                  run_status=model_status, run_started=datetime.now(), run_completed=None,
                                  user=usr, clf_arch=clf_arch, train_summary=train_summary,
                                  dataset_pk=dataset_pk, model_key=model_key)
    new_run.save()

    print 'Run added to db.'
    query = json.loads(Search.objects.get(pk=search_id).query)
    steps = ["preparing data", "training", "done"]
    show_progress = ShowSteps(new_run.pk, steps)
    show_progress.update_view()

    try:
        show_progress.update(0)
        pipe_builder = model_pipeline.get_pipeline_builder()
        pipe_builder.set_pipeline_options(extractor_opt, reductor_opt, normalizer_opt, classifier_opt)
        clf_arch = pipe_builder.pipeline_representation()
        c_pipe, params = pipe_builder.build()

        es_data = EsDataSample(query, field_path, request)
        data_sample_x, data_sample_y, statistics = es_data.get_data_samples()

        show_progress.update(1)
        _start_training_time = time.time()
        model, _s_train = model_pipeline.train_model_with_cv(c_pipe, params, data_sample_x, data_sample_y)
        _total_training_time = time.time() - _start_training_time
        statistics.update(_s_train)
        statistics['time'] = _total_training_time
        statistics['params'] = params
        model_score = "{0:.2f}".format(statistics['f1_score'])
        train_summary = json.dumps(jsonify(statistics))
        show_progress.update(2)
        model_name = 'classifier_{0}.pkl'.format(new_run.pk)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        model_pipeline.save_model(model, output_model_file)
        model_status = 'completed'

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE CLASSIFIER','event':'model_training_failed','args':{'user_name':request.user.username}}),exc_info=True)
        print '--- Error: {0}'.format(e)
        model_status = 'failed'

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE CLASSIFIER',
                                                    'event': 'model_training_completed',
                                                    'args': {'user_name': request.user.username},
                                                    'data': {'run_id': new_run.id}}))
    # declare the job done
    r = ModelClassification.objects.get(pk=new_run.pk)
    r.run_completed = datetime.now()
    r.run_status = model_status
    r.score = model_score
    r.clf_arch = clf_arch
    r.train_summary = train_summary
    r.save()

    print 'job is done'


class ShowSteps(object):
    """ Show model training progress
    """
    def __init__(self, model_pk, steps):
        self.step_messages = steps
        self.n_total = len(steps)
        self.n_step = 0
        self.model_pk = model_pk

    def update(self, step):
        self.n_step = step
        self.update_view()

    def update_view(self):
        i = self.n_step
        r = ModelClassification.objects.get(pk=self.model_pk)
        r.run_status = '{0} [{1}/{2}]'.format(self.step_messages[i], i+1, self.n_total)
        r.save()

