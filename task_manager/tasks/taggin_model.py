

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
