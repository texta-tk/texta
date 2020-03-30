from celery.decorators import task
import secrets
import json
import os

from texta_torch_tagger.tagger import TorchTagger
from texta_tools.text_processor import TextProcessor
from texta_tools.embedding import W2VEmbedding
from texta_tools.mlp_analyzer import get_mlp_analyzer

from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask
from toolkit.elastic.data_sample import DataSample
from toolkit.torchtagger.plots import create_torchtagger_plot
from toolkit.settings import MODELS_DIR
from toolkit.helper_functions import get_core_setting


def get_tokenizer(tokenize):
    tokenizer = None
    if tokenize:
        mlp_url = get_core_setting("TEXTA_MLP_URL")
        mlp_major_version = get_core_setting("TEXTA_MLP_MAJOR_VERSION")
        tokenizer = get_mlp_analyzer(mlp_host=mlp_url, mlp_major_version=mlp_major_version)
    return tokenizer


@task(name="train_torchtagger", base=BaseTask)
def train_torchtagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        model_type = TorchTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # load embedding
        embedding = W2VEmbedding()
        embedding.load_django(tagger_object.embedding)
        # get MLP tokenizer if asked
        tokenizer = get_tokenizer(tagger_object.tokenize)
        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(tagger_object, show_progress=show_progress, join_fields=True)
        show_progress.update_step('training')
        show_progress.update_view(0.0)
        # create TorchTagger
        tagger = TorchTagger(
            embedding,
            tokenizer=tokenizer,
            model_arch=tagger_object.model_architecture
        )
        # train tagger and get result statistics
        tagger_stats = tagger.train(data_sample.data, num_epochs=int(tagger_object.num_epochs))
        # save tagger to disk
        tagger_path = os.path.join(MODELS_DIR, model_type, f'{model_type}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)
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
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise
