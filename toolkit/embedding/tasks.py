from celery.decorators import task
import json

from texta_tools.text_processor import TextProcessor
from texta_tools.embedding import W2VEmbedding

from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.models import Embedding
from toolkit.settings import MODELS_DIR, NUM_WORKERS
from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import get_indices_from_object


@task(name="train_embedding", base=BaseTask)
def train_embedding(embedding_id):
    # retrieve embedding & task objects
    embedding_object = Embedding.objects.get(pk=embedding_id)
    task_object = embedding_object.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('training')
    show_progress.update_view(0)
    try:
        # retrieve indices from project 
        indices = get_indices_from_object(embedding_object)
        field_data = json.loads(embedding_object.fields)
        max_documents = embedding_object.max_documents
        # iterator for texts
        sentences = ElasticSearcher(query=json.loads(embedding_object.query),
                                    indices=indices,
                                    field_data=field_data,
                                    callback_progress=show_progress,
                                    scroll_limit=max_documents)
        # create embedding object & train
        embedding = W2VEmbedding()
        embedding.train(sentences)
        # save model
        show_progress.update_step('saving')
        model_path = embedding_object.generate_name("embedding")
        embedding.save(model_path)
        # save model paths
        embedding_object.embedding_model.name = model_path
        embedding_object.vocab_size = len(embedding.model.wv.vocab)
        embedding_object.save()
        # declare the job done
        task_object.complete()
        return True
    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise
