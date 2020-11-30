import json
import os
import secrets
from celery.decorators import task

from texta_torch_tagger.tagger import TorchTagger
from texta_tools.text_processor import TextProcessor
from texta_tools.embedding import W2VEmbedding
from texta_tools.mlp_analyzer import get_mlp_analyzer

from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.data_sample import DataSample
from toolkit.torchtagger.plots import create_torchtagger_plot
from toolkit.settings import RELATIVE_MODELS_PATH, CELERY_LONG_TERM_TASK_QUEUE
from toolkit.helper_functions import get_core_setting


@task(name="train_torchtagger", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_torchtagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        model_type = TorchTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # load embedding
        embedding = W2VEmbedding()
        # get MLP tokenizer if asked
        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(tagger_object, show_progress=show_progress, join_fields=True)
        show_progress.update_step('training')
        show_progress.update_view(0.0)
        # create TorchTagger
        tagger = TorchTagger(
            embedding,
            model_arch=tagger_object.model_architecture,
            num_epochs=int(tagger_object.num_epochs)
        )
        # train tagger and get result statistics
        tagger_stats = tagger.train(data_sample.data, num_epochs=int(tagger_object.num_epochs))
        # save tagger to disk
        tagger_path = os.path.join(RELATIVE_MODELS_PATH, model_type, f'{model_type}_{tagger_id}_{secrets.token_hex(10)}')
        tagger_path, text_field_path = tagger.save(tagger_path)
        # set tagger location
        tagger_object.model.name = tagger_path
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
        task_object.complete()
        return True

    except Exception as e:
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise
