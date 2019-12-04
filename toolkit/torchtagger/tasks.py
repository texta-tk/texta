from celery.decorators import task
import secrets
import json
import os

from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask
from toolkit.elastic.data_sample import DataSample
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.torchtagger.plots import create_torchtagger_plot
from toolkit.settings import MODELS_DIR


@task(name="torchtagger_train_handler", base=BaseTask)
def torchtagger_train_handler(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        model_type = TorchTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # create Datasample object for retrieving positive and negative sample

        # TODO: Add text_processor

        data_sample = DataSample(tagger_object, show_progress=show_progress, join_fields=True)
        show_progress.update_step('training torchtagger')
        show_progress.update_view(0.0)
        # create TorchTagger
        tagger = TorchTagger(
            tagger_object.id,
            model_arch=tagger_object.model_architecture, 
            num_epochs=int(tagger_object.num_epochs)
        )
        # train tagger and get result statistics
        tagger_stats = tagger.train(data_sample)
        # save tagger to disk
        tagger_path = os.path.join(MODELS_DIR, model_type, f'{model_type}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)
        # set tagger location
        tagger_object.location = json.dumps({model_type: tagger_path})
        # save tagger plot
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_torchtagger_plot(tagger_stats))
        # save label index
        tagger_object.label_index = json.dumps(tagger.label_reverse_index)
        # stats to model object
        tagger_object.f1_score = tagger_stats.f1_score
        tagger_object.precision = tagger_stats.precision
        tagger_object.recall = tagger_stats.recall
        tagger_object.accuracy = tagger_stats.accuracy
        tagger_object.training_loss = tagger_stats.training_loss
        tagger_object.epoch_reports = json.dumps([a.to_dict() for a in tagger.epoch_reports])
        # save tagger object
        tagger_object.save()
        # declare the job done
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        return True

    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise
