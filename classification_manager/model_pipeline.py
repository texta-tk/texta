# -*- coding: utf8 -*-

from datetime import datetime
import hashlib
import json
import logging
import os
import random
import time

# Uses scikit-learn 0.18.1
from sklearn.base import BaseEstimator
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import BernoulliNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import RadiusNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline
from sklearn.externals import joblib
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.model_selection import GridSearchCV

from texta.settings import STATIC_URL, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER
from corpus_tool.models import Search
from classification_manager.data_manager import EsDataSample
from classification_manager.models import ModelClassification
from classification_manager.data_manager import EsDataClassification
from classification_manager.models import JobQueue


class ModelNull(BaseEstimator):

    def fit(self, x, y):
        # Do nothing
        return self

    def transform(self, x):
        # Do nothing
        return x


class ModelStep:

    def __init__(self, name, model, label, params):
        self.name = name
        self.model = model
        self.label = label
        self.params = params

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def get_step(self):
        return (self.name, self.model())

    def get_param(self):
        param_dict = {}
        for k in self.params:
            p_name = '{0}__{1}'.format(self.name, k)
            p_value = self.params[k]
            param_dict[p_name] = p_value
        return param_dict


class PipelineBuilder:
    def __init__(self):
        self.extractor_list = []
        self.reductor_list = []
        self.normalizer_list = []
        self.classifier_list = []
        self.extractor_op = 0
        self.reductor_op = 0
        self.normalizer_op = 0
        self.classifier_op = 0

    def add_extractor(self, name, model, label, params):
        self.extractor_list.append(ModelStep(name, model, label, params))

    def add_reductor(self, name, model, label, params):
        self.reductor_list.append(ModelStep(name, model, label, params))

    def add_normalizer(self, name, model, label, params):
        self.normalizer_list.append(ModelStep(name, model, label, params))

    def add_classifier(self, name, model, label, params):
        self.classifier_list.append(ModelStep(name, model, label, params))

    def get_extractor_options(self):
        options = []
        for i, x in enumerate(self.extractor_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_reductor_options(self):
        options = []
        for i, x in enumerate(self.reductor_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_normalizer_options(self):
        options = []
        for i, x in enumerate(self.normalizer_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_classifier_options(self):
        options = []
        for i, x in enumerate(self.classifier_list):
            options.append({'index': i, 'label': x.label})
        return options

    def set_pipeline_options(self, extractor_op, reductor_op, normalizer_op, classifier_op):
        self.extractor_op = extractor_op
        self.reductor_op = reductor_op
        self.normalizer_op = normalizer_op
        self.classifier_op = classifier_op

    def pipeline_representation(self):
        e = self.extractor_list[self.extractor_op].name
        r = self.reductor_list[self.reductor_op].name
        n = self.normalizer_list[self.normalizer_op].name
        c = self.classifier_list[self.classifier_op].name
        rep = "{0} | {1} | {2} | {3}".format(e, r, n, c)
        return rep

    def build(self):
        # Build model Pipeline
        steps = []
        steps.append(self.extractor_list[self.extractor_op].get_step())
        steps.append(self.reductor_list[self.reductor_op].get_step())
        steps.append(self.normalizer_list[self.normalizer_op].get_step())
        steps.append(self.classifier_list[self.classifier_op].get_step())
        pipe = Pipeline(steps)
        # Build model params for Grid Search
        params = {}
        params.update(self.extractor_list[self.extractor_op].get_param())
        params.update(self.reductor_list[self.reductor_op].get_param())
        params.update(self.normalizer_list[self.normalizer_op].get_param())
        params.update(self.classifier_list[self.classifier_op].get_param())
        return pipe, params


def get_pipeline_builder():

    pipe_builder = PipelineBuilder()

    # Feature Extraction
    params = {'ngram_range': [(1, 1), (1, 2), (1, 3)]}
    pipe_builder.add_extractor('CountVectorizer', CountVectorizer, 'Count Vectorizer', params)

    params = {}
    pipe_builder.add_extractor('HashingVectorizer', HashingVectorizer, 'Hashing Vectorizer', params)

    params = {}
    pipe_builder.add_extractor('TfidfVectorizer', TfidfVectorizer, 'TfIdf Vectorizer', params)

    # Dimension Reduction
    params = {}
    pipe_builder.add_reductor('No_Reduction', ModelNull, 'None', params)

    params = {}
    pipe_builder.add_reductor('TruncatedSVD', TruncatedSVD, 'Truncated SVD', params)

    # Normalization
    params = {}
    pipe_builder.add_normalizer('No_Normalization', ModelNull, 'None', params)

    params = {}
    pipe_builder.add_normalizer('Normalizer', Normalizer, 'Normalizer', params)

    # Classification Models
    params = {}
    pipe_builder.add_classifier('MultinomialNB', MultinomialNB, 'Multinomial Naive Bayes', params)

    params = {}
    pipe_builder.add_classifier('BernoulliNB', BernoulliNB, 'Bernoulli Naive Bayes', params)

    params = {}
    pipe_builder.add_classifier('KNeighborsClassifier', KNeighborsClassifier, 'K-Neighbors', params)

    params = {}
    pipe_builder.add_classifier('RadiusNeighborsClassifier', RadiusNeighborsClassifier, 'Radius Neighbors', params)

    return pipe_builder


def train_model_with_cv(model, params, X, y):

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20)

    # Use Train data to parameter selection in a Grid Search
    gs_clf = GridSearchCV(model, params, n_jobs=1, cv=5)
    gs_clf = gs_clf.fit(X_train, y_train)
    model = gs_clf.best_estimator_

    # Use best model and test data for final evaluation
    y_pred = model.predict(X_test)

    _f1 = f1_score(y_test, y_pred, average='micro')
    _confusion = confusion_matrix(y_test, y_pred)
    __precision = precision_score(y_test, y_pred)
    _recall = recall_score(y_test, y_pred)
    _statistics = {'f1_score': _f1,
                   'confusion_matrix': _confusion,
                   'precision': __precision,
                   'recall': _recall
                   }

    return model, _statistics


def save_model(model, file_name):
    joblib.dump(model, file_name)


def load_model(file_name):
    model = joblib.load(file_name)
    return model


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
        pipe_builder = get_pipeline_builder()
        pipe_builder.set_pipeline_options(extractor_opt, reductor_opt, normalizer_opt, classifier_opt)
        clf_arch = pipe_builder.pipeline_representation()
        c_pipe, params = pipe_builder.build()

        es_data = EsDataSample(query, field_path, request)
        data_sample_x, data_sample_y, statistics = es_data.get_data_samples()

        show_progress.update(1)
        _start_training_time = time.time()
        model, _s_train = train_model_with_cv(c_pipe, params, data_sample_x, data_sample_y)
        _total_training_time = time.time() - _start_training_time
        statistics.update(_s_train)
        statistics['time'] = _total_training_time
        statistics['params'] = params
        model_score = "{0:.2f}".format(statistics['precision'])
        train_summary = json.dumps(jsonify(statistics))
        show_progress.update(2)
        model_name = 'classifier_{0}.pkl'.format(new_run.pk)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        save_model(model, output_model_file)
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


def apply_classifier(job_key):

    job_queue = JobQueue.objects.get(job_key=job_key)

    try:
        model = job_queue.model
        dataset = job_queue.dataset
        query = json.loads(job_queue.search.query)

        es_index = dataset.index
        es_mapping = dataset.mapping
        field_path = model.fields

        if model.run_status == 'completed':
            model_name = 'classifier_{0}.pkl'.format(model.pk)
            output_model_file = os.path.join(MODELS_DIR, model_name)
            clf_model = load_model(output_model_file)
            # Update status
            es_classification = EsDataClassification(es_index, es_mapping, field_path, query)
            _data = es_classification.apply_classifier(clf_model, model.tag_label)
            # Update status
            job_queue.run_status = 'completed'
            job_queue.total_processed = _data['total_processed']
            job_queue.total_positive = _data['total_positive']
            job_queue.total_negative = _data['total_negative']
            job_queue.total_documents = _data['total_documents']
        else:
            # Update status
            job_queue.run_status = 'failed'

    except Exception as e:
        print '- Exception: ', e
        job_queue.run_status = 'failed'

    job_queue.run_completed = datetime.now()
    job_queue.save()


def clean_job_queue():
    jobs = JobQueue.objects.all()
    for j in jobs:
        j.delete()
