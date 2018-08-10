# -*- coding: utf8 -*-

from __future__ import print_function
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
from sklearn.svm import LinearSVC
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
from searcher.models import Search
from task_manager.models import Task
from .data_manager import EsDataClassification, EsDataSample
# from classification_manager.models import JobQueue, ModelClassification
from . import data_manager


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


class TaggingModel:

	def __init__(self):
		self.task_id = None
		self.model = None
		self.model_name = None
		self.description = None
		self.task_model_obj = None
		self.task_id = None
		self.task_model_obj = None

	def train(self, task_id):
		self.task_id = task_id
		self.task_model_obj = Task.objects.get(pk=self.task_id)

		task_params = json.loads(self.task_model_obj.parameters)
		steps = ["preparing data", "training", "saving", "done"]
		show_progress = ShowSteps(self.task_id, steps)
		show_progress.update_view()

		extractor_opt = int(task_params['extractor_opt'])
		reductor_opt = int(task_params['reductor_opt'])
		normalizer_opt = int(task_params['normalizer_opt'])
		classifier_opt = int(task_params['classifier_opt'])

		try:
			show_progress.update(0)
			pipe_builder = get_pipeline_builder()
			pipe_builder.set_pipeline_options(extractor_opt, reductor_opt, normalizer_opt, classifier_opt)
			clf_arch = pipe_builder.pipeline_representation()
			c_pipe, params = pipe_builder.build()

			es_data = EsDataSample(task_params)
			data_sample_x, data_sample_y, statistics = es_data.get_data_samples()

			# Training the model.
			show_progress.update(1)
			self.model, train_summary = self._train_model_with_cv(c_pipe, params, data_sample_x, data_sample_y, self.task_id)

			# Saving the model.
			show_progress.update(2)
			self.save()

			train_summary['model_type'] = 'sklearn'
			model_status = 'Completed'
			show_progress.update(3)

			# Declare the job as done
			r = Task.objects.get(pk=self.task_id)
			r.time_completed = datetime.now()
			r.status = model_status
			r.result = json.dumps(train_summary)
			r.save()

			logging.getLogger(INFO_LOGGER).info(json.dumps({
				'process': 'CREATE CLASSIFIER',
				'event':   'model_training_completed',
				'data':    {'task_id': self.task_id}
			}))

			print('done')

		except Exception as e:
			logging.getLogger(ERROR_LOGGER).error(json.dumps(
				{'process': 'CREATE CLASSIFIER', 'event': 'model_training_failed', 'data': {'task_id': self.task_id}}), exc_info=True)

			# declare the job as failed.
			r = Task.objects.get(pk=self.task_id)
			r.time_completed = datetime.now()
			r.status = 'Failed'
			r.result = json.dumps({'error': repr(e)})
			r.save()

	def tag(self, texts):
		return self.model.predict(texts)

	def delete(self):
		pass

	def save(self):
		"""
		Saves trained model as a pickle to the filesystem.
		:rtype: bool
		"""
		try:
			model_name = 'model_{0}'.format(self.task_id)
			self.model_name = model_name
			output_model_file = os.path.join(MODELS_DIR, model_name)
			joblib.dump(self.model, output_model_file)
			return True

		except Exception as e:
			model_name = 'model_{0}'.format(self.task_id)
			file_path = os.path.join(MODELS_DIR, model_name)
			logging.getLogger(ERROR_LOGGER).error('Failed to save model to filesystem.', exc_info=True, extra={
				'model_name': model_name,
				'file_path':  file_path
			})

	def load(self, model_id):
		"""
		Imports model pickle from filesystem.
		:param model_id: id of task it was saved from.
		:return: serialized model pickle.
		"""
		try:
			model_name = 'model_{0}'.format(model_id)
			model_file = os.path.join(MODELS_DIR, model_name)
			model = joblib.load(model_file)
			self.model = model
			self.task_id = int(model_id)
			self.description = Task.objects.get(pk=self.task_id).description
			return model

		except Exception as e:
			model_name = 'model_{0}'.format(model_id)
			file_path = os.path.join(MODELS_DIR, model_name)
			logging.getLogger(ERROR_LOGGER).error('Failed to save model to filesystem.', exc_info=True, extra={
				'model_name': model_name,
				'file_path':  file_path
			})

	def _training_process(self):
		pass

	@staticmethod
	def _train_model_with_cv(model, params, X, y, task_id):

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
		_statistics = {
			'f1_score':         round(_f1, 3),
			'confusion_matrix': _confusion.tolist(),
			'precision':        round(__precision, 3),
			'recall':           round(_recall, 3)
		}

		return model, _statistics


def get_pipeline_builder():
	pipe_builder = PipelineBuilder()

	# Feature Extraction
	params = {'ngram_range': [(1, 1), (1, 2), (1, 3)], 'min_df': [5]}
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
	pipe_builder.add_classifier('LinearSVC', LinearSVC, 'LinearSVC', params)

	params = {}
	pipe_builder.add_classifier('BernoulliNB', BernoulliNB, 'Bernoulli Naive Bayes', params)

	params = {}
	pipe_builder.add_classifier('KNeighborsClassifier', KNeighborsClassifier, 'K-Neighbors', params)

	params = {}
	pipe_builder.add_classifier('RadiusNeighborsClassifier', RadiusNeighborsClassifier, 'Radius Neighbors', params)

	return pipe_builder


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
		r = Task.objects.get(pk=self.model_pk)
		r.status = '{0} [{1}/{2}]'.format(self.step_messages[i], i + 1, self.n_total)
		r.save()

#
# def apply_classifier(job_key):
#
#     job_queue = JobQueue.objects.get(job_key=job_key)
#
#     try:
#         model = job_queue.model
#         dataset = job_queue.dataset
#         query = json.loads(job_queue.search.query)
#
#         es_index = dataset.index
#         es_mapping = dataset.mapping
#         field_path = model.fields
#
#         if model.run_status == 'Completed':
#             model_name = 'classifier_{0}.pkl'.format(model.pk)
#             output_model_file = os.path.join(MODELS_DIR, model_name)
#             clf_model = load_model(output_model_file)
#             # Update status
#             es_classification = EsDataClassification(es_index, es_mapping, field_path, query)
#             _data = es_classification.apply_classifiers([clf_model], [model.tag_label])
#             # Update status
#             job_queue.run_status = 'Completed'
#             job_queue.total_processed = _data['total_processed']
#             job_queue.total_positive = _data['total_positive']
#             job_queue.total_negative = _data['total_negative']
#             job_queue.total_documents = _data['total_documents']
#         else:
#             # Update status
#             job_queue.run_status = 'failed'
#
#     except Exception as e:
#         print('- Exception: ', e)
#         job_queue.run_status = 'failed'
#
#     job_queue.run_completed = datetime.now()
#     job_queue.save()
#
#
# def clean_job_queue():
#     jobs = JobQueue.objects.all()
#     for j in jobs:
#         j.delete()
#
