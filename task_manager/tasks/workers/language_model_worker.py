
import json
import logging
import os

from gensim.models import word2vec

from task_manager.models import Task
from task_manager.tools import EsIterator
from task_manager.tools import ShowProgress
from task_manager.tools import TaskCanceledException
from texta.settings import ERROR_LOGGER, INFO_LOGGER, MODELS_DIR

from .base_worker import BaseWorker


class LanguageModelWorker(BaseWorker):

    def __init__(self):
        self.id = None
        self.model = None
        self.model_name = None

    def run(self, task_id):

        self.id = task_id
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_started', 'data': {'task_id': self.id}}))

        num_passes = 5
        # Number of word2vec passes + one pass to vocabulary building
        total_passes = num_passes + 1
        show_progress = ShowProgress(self.id, multiplier=total_passes)
        show_progress.update_view(0)
        model = word2vec.Word2Vec()

        task_params = json.loads(Task.objects.get(pk=self.id).parameters)

        try:
            sentences = EsIterator(task_params, callback_progress=show_progress)
            model = word2vec.Word2Vec(
                sentences,
                min_count=int(task_params['min_freq']),
                size=int(task_params['num_dimensions']),
                workers=int(task_params['num_workers']),
                iter=int(num_passes)
            )
            
            # Save model
            self.model = model
            self.save()

            # declare the job done
            show_progress.update_view(100.0)
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_completed', 'data': {'task_id': self.id}}))
            task = Task.objects.get(pk=self.id)
            task.result = json.dumps({"model_type": "word2vec", "lexicon_size": len(self.model.wv.vocab)})
            task.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

        except TaskCanceledException as e:
            # If here, task was canceled while training
            # Delete task
            task = Task.objects.get(pk=self.id)
            task.delete()
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_canceled', 'data': {'task_id': self.id}}), exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            # If here, internal error happened
            logging.getLogger(ERROR_LOGGER).exception(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_failed', 'data': {'task_id': self.id}}), exc_info=True)
            print('--- Error: {0}'.format(e))
            # Declare the job as failed
            task = Task.objects.get(pk=self.id)
            task.update_status(Task.STATUS_FAILED, set_time_completed=True)

        print('done')

    def delete(self):
        pass

    def save(self):
        try:
            model_name = 'model_' + str(self.id)
            self.model_name = model_name
            output_model_file = os.path.join(MODELS_DIR, model_name)
            self.model.save(output_model_file)
            return True

        except Exception as e:
            model_name = 'model_' + str(self.id)
            filepath = os.path.join(MODELS_DIR, model_name)
            logging.getLogger(ERROR_LOGGER).error('Failed to save model pickle to filesystem.', exc_info=True, extra={'filepath': filepath, 'modelname': model_name})
