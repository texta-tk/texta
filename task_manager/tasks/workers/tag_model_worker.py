
import os
import json
import logging

from task_manager.models import Task
from task_manager.tools import EsDataSample
from searcher.models import Search
from utils.es_manager import ES_Manager
from utils.datasets import Datasets

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from texta.settings import MODELS_DIR

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.externals import joblib
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.model_selection import GridSearchCV
from task_manager.tools import ShowSteps
from task_manager.tools import get_pipeline_builder

from .base_worker import BaseWorker


class TagModelWorker(BaseWorker):

	def __init__(self):
		self.task_id = None
		self.model = None
		self.model_name = None
		self.description = None
		self.task_model_obj = None
		self.task_id = None
		self.task_model_obj = None

	def run(self, task_id):
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
			# clf_arch = pipe_builder.pipeline_representation()
			c_pipe, c_params = pipe_builder.build()

			param_field = task_params['field']
			# Check if query was explicitly set
			if 'search_tag' in task_params:
				# Use set query
				param_query = task_params['search_tag']
			else:
				# Otherwise, load query from saved search
				param_query = json.loads(Search.objects.get(pk=int(task_params['search'])).query)

			# Build Data sampler
			ds = Datasets().activate_dataset_by_id(task_params['dataset'])
			es_m = ds.build_manager(ES_Manager)
			es_data = EsDataSample(field=param_field, query=param_query, es_m=es_m)
			data_sample_x, data_sample_y, statistics = es_data.get_data_samples()

			# Training the model.
			show_progress.update(1)
			self.model, train_summary = self._train_model_with_cv(c_pipe, c_params, data_sample_x, data_sample_y, self.task_id)
			train_summary['samples'] = statistics

			# Saving the model.
			show_progress.update(2)
			self.save()

			train_summary['model_type'] = 'sklearn'
			show_progress.update(3)

			# Declare the job as done
			r = Task.objects.get(pk=self.task_id)
			r.result = json.dumps(train_summary)
			r.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

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
			r.result = json.dumps({'error': repr(e)})
			r.update_status(Task.STATUS_FAILED, set_time_completed=True)

	def tag(self, texts):
		return self.model.predict(texts)

	def delete(self):
		pass

	def save(self):
		"""
		Saves trained model as a pickle to the filesystem.
		:rtype: bool
		"""
		model_name = 'model_{0}'.format(self.task_id)
		self.model_name = model_name
		output_model_file = os.path.join(MODELS_DIR, model_name)
		try:
			joblib.dump(self.model, output_model_file)
			return True

		except Exception as e:
			logging.getLogger(ERROR_LOGGER).error('Failed to save model to filesystem.', exc_info=True, extra={
				'model_name': model_name,
				'file_path':  output_model_file
			})

	def load(self, task_id):
		"""
		Imports model pickle from filesystem.
		:param task_id: id of task it was saved from.
		:return: serialized model pickle.
		"""
		model_name = 'model_{0}'.format(task_id)
		file_path = os.path.join(MODELS_DIR, model_name)
		try:
			model = joblib.load(file_path)
			self.model = model
			self.task_id = int(task_id)
			self.description = Task.objects.get(pk=self.task_id).description
			return model

		except Exception as e:
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
