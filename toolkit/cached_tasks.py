import os
from typing import List

from celery import Celery, shared_task
from texta_embedding.embedding import Embedding
from texta_tools.text_processor import TextProcessor

from toolkit.taskman import app
from toolkit.base_tasks import BaseTask
from toolkit.settings import CELERY_CACHED_TASK_QUEUE


# OBJECT FOR HOLDING THE EMBEDDINGS SO THEY WON'T RELOAD ON EACH REQUEST
CACHE = {}


def load_embedding(embedding_path: str):
    global CACHE
    if embedding_path not in CACHE:
        embedding = Embedding()
        embedding.load(embedding_path)
        CACHE[embedding_path] = embedding


@app.task(name="cached_embedding_get_similar", base=BaseTask, queue=CELERY_CACHED_TASK_QUEUE)
def cached_embedding_get_similar(
        positives_used: List,
        negatives_used: List,
        positives_unused: List,
        negatives_unused: List,
        n_similar: int,
        embedding_path: str
    ):
    try:
        load_embedding(embedding_path)
        return CACHE[embedding_path].get_similar(
            positives_used,
            negatives_used = negatives_used,
            positives_unused = positives_unused,
            negatives_unused = negatives_unused,
            n=n_similar
        )
    except Exception as e:
        return {"worker_error": e}


@app.task(name="cached_embedding_phrase", base=BaseTask, queue=CELERY_CACHED_TASK_QUEUE)
def cached_embedding_phrase(text: str, embedding_path: str):
    try:
        load_embedding(embedding_path)
        phraser = CACHE[embedding_path].phraser
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=False)
        return text_processor.process(text)
    except Exception as e:
        return {"worker_error": e}
