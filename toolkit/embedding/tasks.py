from celery.decorators import task
from gensim.models import word2vec

from toolkit.embedding.models import Embedding
from toolkit.core.task.models import Task
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.phraser import Phraser
from toolkit.tools.text_processor import TextProcessor
from toolkit.settings import MODELS_DIR, NUM_WORKERS

import json
import os


@task(name="train_embedding")
def train_embedding(embedding_id):
    # retrieve embedding & task objects
    embedding_object = Embedding.objects.get(pk=embedding_id)
    task_object = embedding_object.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('phraser')
    show_progress.update_view(0)

    # parse field data
    field_data = [ElasticSearcher().core.decode_field_data(field) for field in embedding_object.fields]
    # create itrerator for phraser
    text_processor = TextProcessor(sentences=True, remove_stop_words=True, tokenize=True)
    sentences = ElasticSearcher(query=json.loads(embedding_object.query), field_data=field_data, output='text', callback_progress=show_progress, text_processor=text_processor)
    # build phrase model
    phraser = Phraser(embedding_id)
    phraser.build(sentences)

    # Number of word2vec passes + one pass to vocabulary building
    num_passes = 5
    total_passes = num_passes + 1

    # update progress
    show_progress = ShowProgress(task_object, multiplier=total_passes)
    show_progress.update_step('word2vec')
    show_progress.update_view(0)

    # build new processor with phraser
    text_processor = TextProcessor(phraser=phraser, sentences=True, remove_stop_words=True, tokenize=True)

    # iterate again with built phrase model to include phrases in language model
    sentences = ElasticSearcher(query=json.loads(embedding_object.query), field_data=field_data, output='text', callback_progress=show_progress, text_processor=text_processor)
    model = word2vec.Word2Vec(sentences, min_count=embedding_object.min_freq, size=embedding_object.num_dimensions, workers=NUM_WORKERS, iter=int(num_passes))

    # Save models
    show_progress.update_step('saving')
    model_path = os.path.join(MODELS_DIR, 'embedding', 'embedding_'+str(embedding_id))
    phraser_path = os.path.join(MODELS_DIR, 'embedding', 'phraser_'+str(embedding_id))
    model.save(model_path)
    phraser.save(phraser_path)

    # save model locations
    embedding_object.location = json.dumps({'embedding': model_path, 'phraser': phraser_path})
    embedding_object.vocab_size = len(model.wv.vocab)
    embedding_object.save()

    # declare the job done
    show_progress.update_step('')
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
