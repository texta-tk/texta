import json
import os
import secrets

from celery.decorators import task
from gensim.models import word2vec

from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.models import Embedding
from toolkit.embedding.phraser import Phraser
from toolkit.settings import MODELS_DIR, NUM_WORKERS
from toolkit.tools.show_progress import ShowProgress
from toolkit.tools.text_processor import TextProcessor
from toolkit.helper_functions import get_indices_from_object


@task(name="train_embedding", base=BaseTask, queue="long_term_tasks")
def train_embedding(embedding_id):
    # retrieve embedding & task objects
    embedding_object = Embedding.objects.get(pk=embedding_id)
    task_object = embedding_object.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('building phraser')
    show_progress.update_view(0)

    try:
        # retrieve indices from project 
        indices = get_indices_from_object(embedding_object)
        field_data = json.loads(embedding_object.fields)
        max_documents = embedding_object.max_documents

        # create itrerator for phraser
        text_processor = TextProcessor(sentences=True, remove_stop_words=True, tokenize=True)
        sentences = ElasticSearcher(query=json.loads(embedding_object.query),
                                    indices=indices,
                                    field_data=field_data,
                                    output=ElasticSearcher.OUT_TEXT,
                                    callback_progress=show_progress,
                                    scroll_limit=max_documents,
                                    text_processor=text_processor)

        # build phrase model
        phraser = Phraser(embedding_id)
        phraser.build(sentences)

        # Number of word2vec passes + one pass to vocabulary building
        num_passes = 5
        total_passes = num_passes + 1

        # update progress
        show_progress = ShowProgress(task_object, multiplier=total_passes)
        show_progress.update_step('building embedding')
        show_progress.update_view(0)

        # build new processor with phraser
        text_processor = TextProcessor(phraser=phraser, sentences=True, remove_stop_words=True, tokenize=True)

        # iterate again with built phrase model to include phrases in language model
        sentences = ElasticSearcher(query=json.loads(embedding_object.query),
                                    indices=indices,
                                    field_data=field_data,
                                    output=ElasticSearcher.OUT_TEXT,
                                    callback_progress=show_progress,
                                    scroll_limit=max_documents,
                                    text_processor=text_processor)
        # word2vec model
        model = word2vec.Word2Vec(
            sentences,
            min_count=embedding_object.min_freq,
            size=embedding_object.num_dimensions,
            iter=int(num_passes),
            workers=NUM_WORKERS
        )

        # Save models
        show_progress.update_step('saving')
        full_model_path, relative_model_path = embedding_object.generate_name("embedding")
        full_phraser_path, relative_phraser_path = embedding_object.generate_name("phraser")
        model.save(full_model_path)
        phraser.save(full_phraser_path)

        # save model paths
        embedding_object.embedding_model.name = relative_model_path
        embedding_object.phraser_model.name = relative_phraser_path
        embedding_object.vocab_size = len(model.wv.vocab)
        embedding_object.save()

        # declare the job done
        task_object.complete()
        return True

    except Exception as e:
        # declare the job failed
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise
