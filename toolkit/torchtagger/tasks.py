from celery.decorators import task
import json

from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask
from toolkit.torchtagger.data_sample import DataSample
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.embedding.views import global_w2v_cache


@task(name="torchtagger_train_handler", base=BaseTask)
def torchtagger_train_handler(tagger_id, testing=False):
    # retrieve neurotagger & task objects
    tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)
    task_object = tagger_object.task
    embedding_model = global_w2v_cache.get_model(tagger_object.embedding)

    show_progress = ShowProgress(task_object, multiplier=1)
    # create Datasample object for retrieving positive and negative sample
    data_sample = DataSample(tagger_object, show_progress=show_progress, join_fields=True)

    tagger = TorchTagger(embedding_model, model_arch=tagger_object.model_architecture)
    tagger.train(data_sample)
