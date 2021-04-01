from celery.decorators import task
from django.db import connections
import json

from texta_tools.text_processor import TextProcessor

from toolkit.base_tasks import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.tools.lemmatizer import ElasticLemmatizer
from toolkit.embedding.models import Embedding
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE

from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import get_indices_from_object


@task(name="train_embedding", base=BaseTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
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
        use_phraser = embedding_object.use_phraser
        snowball_language = embedding_object.snowball_language
        # add stemmer if asked
        if snowball_language:
            snowball_lemmatizer = ElasticLemmatizer(language=snowball_language)
        else:
            snowball_lemmatizer = None
        # iterator for texts
        sentences = ElasticSearcher(query=json.loads(embedding_object.query),
                                    indices=indices,
                                    field_data=field_data,
                                    callback_progress=show_progress,
                                    scroll_limit=max_documents,
                                    text_processor=TextProcessor(sentences=True, remove_stop_words=True, words_as_list=True, lemmatizer=snowball_lemmatizer),
                                    output=ElasticSearcher.OUT_TEXT)
        # create embedding object & train
        embedding = embedding_object.get_embedding()
        embedding.train(sentences, use_phraser=use_phraser)

        # close all db connections
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        # save model
        show_progress.update_step('saving')
        full_model_path, relative_model_path = embedding_object.generate_name("embedding")
        embedding.save(full_model_path)

        # save model path
        embedding_object.embedding_model.name = relative_model_path
        embedding_object.vocab_size = embedding.model.wv.vectors.shape[0]
        embedding_object.save()
        # declare the job done
        task_object.complete()
        return True
    except Exception as e:
        # declare the job failed
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise
