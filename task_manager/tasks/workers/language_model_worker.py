import json
import logging
import os

from gensim.models import word2vec

from utils.helper_functions import create_file_path, write_task_xml
from task_manager.models import Task
from task_manager.tools import EsIterator
from task_manager.tools import ShowProgress
from task_manager.tools import TaskCanceledException
from texta.settings import MODELS_DIR, ERROR_LOGGER, INFO_LOGGER
from utils.word_cluster import WordCluster
from utils.phraser import Phraser
import graypy

from .base_worker import BaseWorker


class LanguageModelWorker(BaseWorker):

    def __init__(self):
        self._reload_env()
        self.info_logger, self.error_logger = self._generate_loggers()

        self.id = None
        self.model = None
        self.model_name = None
        self.phraser_name = None
        self.task_obj = None
        self.task_type = None
        self.word_cluster = None
        self.phraser = None

    def _reload_env(self):
        from dotenv import load_dotenv
        from pathlib import Path
        env_path = str(Path('.env'))
        load_dotenv(dotenv_path=env_path)

    def _generate_loggers(self):
        info_logger = logging.getLogger(INFO_LOGGER)
        error_logger = logging.getLogger(ERROR_LOGGER)

        handler = graypy.GELFUDPHandler(os.getenv("GRAYLOG_HOST_NAME", "localhost"), int(os.getenv("GRAYLOG_PORT", 12201)))

        info_logger.addHandler(handler)
        error_logger.addHandler(handler)

        return info_logger, error_logger

    def run(self, task_id):
        self.id = task_id
        self.task_obj = Task.objects.get(pk=self.id)
        self.task_type = self.task_obj.task_type

        log_dict = {'task': 'CREATE MODEL', 'event': 'model_training_started', 'data': {'task_id': self.id}}
        self.info_logger.info("Created model", extra=log_dict)

        num_passes = 5
        # Number of word2vec passes + one pass to vocabulary building
        total_passes = num_passes + 1
        task_params = json.loads(self.task_obj.parameters)

        try:
            show_progress = ShowProgress(self.id, multiplier=1)
            show_progress.update_step('Phraser')
            show_progress.update_view(0)

            sentences = EsIterator(task_params, callback_progress=show_progress)

            # build phrase model
            phraser = Phraser(task_id)
            phraser.build(sentences)

            # update progress
            show_progress = ShowProgress(self.id, multiplier=total_passes)
            show_progress.update_step('W2V')
            show_progress.update_view(0)

            # iterate again with built phrase model to include phrases in language model
            sentences = EsIterator(task_params, callback_progress=show_progress, phraser=phraser)

            model = word2vec.Word2Vec(
                sentences,
                min_count=int(task_params['min_freq']),
                size=int(task_params['num_dimensions']),
                workers=int(task_params['num_workers']),
                iter=int(num_passes)
            )

            show_progress.update_step('Cluster')
            show_progress.update_view(100.0)

            # create cluster model
            self.word_cluster = WordCluster()
            self.word_cluster.cluster(model)

            # Save model
            self.model = model
            self.phraser = phraser
            show_progress.update_step('Saving')
            self.save()

            # declare the job done
            show_progress.update_step(None)
            show_progress.update_view(100.0)

            log_dict = {'task': 'CREATE MODEL', 'event': 'model_training_completed', 'data': {'task_id': self.id}}
            self.info_logger.info("Finished model training", extra=log_dict)

            self.task_obj.result = json.dumps({"model_type": "word2vec", "lexicon_size": len(self.model.wv.vocab)})
            # self.task_obj.resources = {"word_cluster": self.word_cluster}
            self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

        except TaskCanceledException as e:
            # If here, task was canceled while training
            # Delete task
            self.task_obj.delete()
            log_dict = {'task': 'CREATE MODEL', 'event': 'model_training_canceled', 'data': {'task_id': self.id}}
            self.info_logger.info("Model training canceled", extra=log_dict, exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            # If here, internal error happened
            log_dict = {'task': 'CREATE MODEL', 'event': 'model_training_failed', 'data': {'task_id': self.id}}
            self.error_logger.exception("Model training failed", extra=log_dict, exc_info=True)
            # print('--- Error: {0}'.format(e))
            # Declare the job as failed
            self.task_obj.result = json.dumps({"error": str(e)})
            self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=False)

    def delete(self):
        pass

    def save(self):
        try:
            log_dict = {'task': 'SAVE LANGUAGE MODEL', 'event': 'Starting to save language model', 'data': {'task_id': self.id}}
            self.info_logger.info("Saving language model", extra=log_dict)

            model_name = 'model_{}'.format(self.task_obj.unique_id)
            phraser_name = 'phraser_{}'.format(self.task_obj.unique_id)
            cluster_name = 'cluster_{}'.format(self.task_obj.unique_id)
            xml_name = 'xml_{}'.format(self.task_obj.unique_id)

            output_model_file = create_file_path(model_name, MODELS_DIR, self.task_type)
            output_phraser_file = create_file_path(phraser_name, MODELS_DIR, self.task_type)
            output_cluster_file = create_file_path(cluster_name, MODELS_DIR, self.task_type)
            output_xml_file = create_file_path(xml_name, MODELS_DIR, self.task_type)

            self.model.save(output_model_file)
            self.phraser.save(output_phraser_file)
            self.word_cluster.save(output_cluster_file)

            write_task_xml(self.task_obj, output_xml_file)

            log_dict = {'task': 'SAVE LANGUAGE MODEL', 'event': 'Saving finished', 'data': {'output_model_file': output_model_file, 'output_phraser_file': output_phraser_file, 'task_id': self.id}}
            self.info_logger.info("Finished saving language model", extra=log_dict)
            return True

        except Exception as e:
            filepath = os.path.join(MODELS_DIR, self.model_name)
            self.error_logger.error('Failed to save model pickle to filesystem.', exc_info=True, extra={'filepath': filepath, 'modelname': self.model_name, 'task_id': self.id})
