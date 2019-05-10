
import os
import json
import logging
import numpy as np
import pandas as pd

from task_manager.models import Task
from task_manager.tools import EsDataSample
from searcher.models import Search
from utils.es_manager import ES_Manager
from utils.datasets import Datasets
from utils.word_cluster import WordCluster

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from texta.settings import MODELS_DIR
from texta.settings import MEDIA_URL
from texta.settings import PROTECTED_MEDIA
from texta.settings import URL_PREFIX

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.externals import joblib
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.model_selection import GridSearchCV
from task_manager.tools import ShowSteps
from task_manager.tools import TaskCanceledException
from task_manager.tools import get_pipeline_builder
from utils.helper_functions import plot_confusion_matrix, create_file_path, write_task_xml
from utils.stop_words import StopWords
from utils.phraser import Phraser

from .base_worker import BaseWorker


class TagModelWorker(BaseWorker):

    def __init__(self):
        self.task_id = None
        self.model = None
        self.model_name = None
        self.description = None
        self.task_obj = None
        self.task_params = None
        self.task_type = None
        self.n_jobs = 1

    def _handle_language_model(self, data_sample_x_map):
        if 'language_model' in self.task_params:
            language_model = self.task_params['language_model']

            if 'word_cluster_fields' in self.task_params:
                word_cluster_fields = self.task_params['word_cluster_fields']
            else:
                word_cluster_fields = None


            task_obj = Task.objects.get(pk=int(language_model['pk']))
            sw = StopWords()

            # detect phrases & remove stopwords
            phraser = Phraser(int(language_model['pk']))
            phraser.load()
            if phraser:
                for field_name, field_content in data_sample_x_map.items():
                    field_content = [' '.join(phraser.phrase(sw.remove(text).split(' '))) for text in field_content]
                    data_sample_x_map[field_name] = field_content

            # cluster if asked
            if word_cluster_fields:
                wc = WordCluster()
                loaded = wc.load(task_obj.unique_id)
                if loaded:
                    for word_cluster_field in word_cluster_fields:
                        if word_cluster_field in data_sample_x_map:
                            data_sample_x_map[word_cluster_field] = [wc.text_to_clusters(text) for text in data_sample_x_map[word_cluster_field]]


    def run(self, task_id):

        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.task_type = self.task_obj.task_type

        self.task_params = json.loads(self.task_obj.parameters)
        steps = ["preparing data", "training", "saving", "done"]
        show_progress = ShowSteps(self.task_id, steps)
        show_progress.update_view()

        extractor_opt = int(self.task_params['extractor_opt'])
        reductor_opt = int(self.task_params['reductor_opt'])
        normalizer_opt = int(self.task_params['normalizer_opt'])
        classifier_opt = int(self.task_params['classifier_opt'])
        negative_set_multiplier = float(self.task_params['negative_multiplier_opt'])
        max_sample_size_opt = int(self.task_params['max_sample_size_opt'])
        score_threshold_opt = float(self.task_params['score_threshold_opt'])

        if 'num_threads' in self.task_params:
            self.n_jobs = int(self.task_params['num_threads'])

        try:
            if 'fields' in self.task_params:
                fields = self.task_params['fields']
            else:
                fields = [self.task_params['field']]

            show_progress.update(0)
            pipe_builder = get_pipeline_builder()
            pipe_builder.set_pipeline_options(extractor_opt, reductor_opt, normalizer_opt, classifier_opt)
            # clf_arch = pipe_builder.pipeline_representation()
            c_pipe, c_params = pipe_builder.build(fields=fields)

            # Check if query was explicitly set
            if 'search_tag' in self.task_params:
                # Use set query
                param_query = self.task_params['search_tag']
            else:
                # Otherwise, load query from saved search
                param_query = self._parse_query(self.task_params)

            # Build Data sampler
            ds = Datasets().activate_datasets_by_id(self.task_params['dataset'])
            es_m = ds.build_manager(ES_Manager)
            self.model_name = 'model_{0}'.format(self.task_obj.unique_id)
            es_data = EsDataSample(fields=fields, 
                                   query=param_query,
                                   es_m=es_m,
                                   negative_set_multiplier=negative_set_multiplier,
                                   max_positive_sample_size=max_sample_size_opt,
                                   score_threshold=score_threshold_opt)
            data_sample_x_map, data_sample_y, statistics = es_data.get_data_samples()
            # Pass data_sample_x_map as reference to be modified by self._handle_language_model
            self._handle_language_model(data_sample_x_map)

            # Training the model.
            show_progress.update(1)
            self.model, train_summary, plot_url = self._train_model_with_cv(c_pipe, c_params, data_sample_x_map, data_sample_y)
            train_summary['samples'] = statistics
            train_summary['confusion_matrix'] = '<img src="{}" style="max-width: 80%">'.format(plot_url)
            # Saving the model.
            show_progress.update(2)
            self.save()

            train_summary['model_type'] = 'sklearn'
            show_progress.update(3)

            # Declare the job as done
            self.task_obj.result = json.dumps(train_summary)
            self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

            log_dict = {
                'task': 'CREATE CLASSIFIER',
                'event': 'model_training_completed',
                'data': {'task_id': self.task_id}
            }
            logging.getLogger(INFO_LOGGER).info("Model training complete", extra=log_dict)

        except TaskCanceledException as e:
            # If here, task was canceled while training
            # Delete task
            self.task_obj.delete()
            log_dict = {'task': 'CREATE CLASSIFIER', 'event': 'model_training_canceled', 'data': {'task_id': self.task_id}}
            logging.getLogger(INFO_LOGGER).info("Model training canceled", extra=log_dict, exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            log_dict = {'task': 'CREATE CLASSIFIER', 'event': 'model_training_failed', 'data': {'task_id': self.task_id}}
            logging.getLogger(ERROR_LOGGER).exception("Model training failed", extra=log_dict, exc_info=True)
            # declare the job as failed.
            self.task_obj.result = json.dumps({'error': repr(e)})
            self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=True)
        
        print('done')

    def tag(self, text_map, check_map_consistency=True):
        # Recover features from model to check map
        union_features = [x[0] for x in self.model.named_steps['union'].transformer_list if x[0].startswith('pipe_')]
        field_features = [x[5:] for x in union_features]
        df_text = pd.DataFrame(text_map)
        for field in field_features:
            if field not in text_map:
                if check_map_consistency:
                    raise RuntimeError("Mapped field not present: {}".format(field))
                else:
                    df_text[field] = ""
        # Predict        
        return self.model.predict(df_text)

    def delete(self):
        pass

    def save(self):
        """
        Saves trained model as a pickle to the filesystem.
        :rtype: bool
        """
        # create_file_path from helper_functions creates missing folders and returns a path
        output_model_file = create_file_path(self.model_name, MODELS_DIR, self.task_type)
        xml_name = self.model_name.replace('model_', 'xml_')
        output_xml_file = create_file_path(xml_name, MODELS_DIR, self.task_type)

        try:
            joblib.dump(self.model, output_model_file)
            write_task_xml(self.task_obj, output_xml_file)
            return True

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error('Failed to save model to filesystem.', exc_info=True, extra={
                'model_name': self.model_name,
                'file_path':  output_model_file
            })

    def load(self, task_id):
        """
        Imports model pickle from filesystem.
        :param task_id: id of task it was saved from.
        :return: serialized model pickle.
        """
        self.task_obj = Task.objects.get(pk=task_id)
        model_name = 'model_{}'.format(self.task_obj.unique_id)
        self.task_type = self.task_obj.task_type
        file_path = os.path.join(MODELS_DIR, self.task_type, model_name)
        try:
            model = joblib.load(file_path)
            self.model = model
            self.task_id = int(task_id)
            self.description = self.task_obj.description
            return model

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error('Failed to load model from the filesystem.', exc_info=True, extra={
                'model_name': model_name,
                'file_path':  file_path
            })

    def _training_process(self):
        pass

    def _train_model_with_cv(self, model, params, X_map, y):
        fields = list(X_map.keys())
        X_train = {}
        X_test = {}
        for field in fields:
            X_train[field], X_test[field], y_train, y_test = train_test_split(X_map[field], y, test_size=0.20, random_state=42)

        df_train = pd.DataFrame(X_train)
        df_test = pd.DataFrame(X_test)

        # Use Train data to parameter selection in a Grid Search
        gs_clf = GridSearchCV(model, params, n_jobs=self.n_jobs, cv=5, verbose=1)
        gs_clf = gs_clf.fit(df_train, y_train)
        model = gs_clf.best_estimator_
        # Use best model and test data for final evaluation
        y_pred = model.predict(df_test)
        # Report
        _f1 = f1_score(y_test, y_pred, average='micro')
        _confusion = confusion_matrix(y_test, y_pred)

        # Plotting
        plt = plot_confusion_matrix(_confusion, classes=["negative", "positive"])
        plot_name = "{}_cm.svg".format(self.model_name)
        plot_path = create_file_path(plot_name, PROTECTED_MEDIA, "task_manager/", self.task_type)
        plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager/", self.task_type, plot_name)
        plt.savefig(plot_path, format="svg", bbox_inches='tight')

        __precision = precision_score(y_test, y_pred)
        _recall = recall_score(y_test, y_pred)
        _statistics = {
            'f1_score':         round(_f1, 3),
            'confusion_matrix': _confusion.tolist(),
            'precision':        round(__precision, 3),
            'recall':           round(_recall, 3)
        }

        return model, _statistics, plot_url
