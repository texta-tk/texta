from celery.decorators import task
import secrets
import json
import os

from toolkit.helper_functions import get_indices_from_object
from toolkit.tools.text_processor import TextProcessor
from toolkit.embedding.phraser import Phraser
from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask
from toolkit.elastic.data_sample import DataSample
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.torchtagger.plots import create_torchtagger_plot
from toolkit.settings import MODELS_DIR


@task(name="train_torchtagger", base=BaseTask)
def train_torchtagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        model_type = TorchTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)

        fields = json.loads(tagger_object.fields)
        indices = get_indices_from_object(tagger_object)

        # load embedding and create text processor
        # TODO: investigate if stop words should not be removed
        if tagger_object.embedding:
            phraser = Phraser(embedding_id=tagger_object.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True)
        else:
            text_processor = TextProcessor(remove_stop_words=True)

        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(tagger_object, indices=indices, field_data=fields, show_progress=show_progress, join_fields=True)

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
        tagger_path, text_field_path = tagger.save(tagger_path)
        # set tagger location
        tagger_object.model.name = tagger_path
        # set text_field location
        tagger_object.text_field.name = text_field_path
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
