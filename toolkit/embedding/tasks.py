import os
import json
import secrets

from celery.decorators import task
from gensim.models import word2vec

from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.word_cluster import WordCluster
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.core.task.models import Task
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.phraser import Phraser
from toolkit.tools.text_processor import TextProcessor
from toolkit.settings import MODELS_DIR, NUM_WORKERS
from toolkit.base_task import BaseTask


@task(name="train_embedding", base=BaseTask)
def train_embedding(embedding_id):
    # retrieve embedding & task objects
    embedding_object = Embedding.objects.get(pk=embedding_id)
    task_object = embedding_object.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('building phraser')
    show_progress.update_view(0)

    try:
        # retrieve indices from project 
        indices = embedding_object.project.indices
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
        model = word2vec.Word2Vec(sentences,
                                  min_count=embedding_object.min_freq,
                                  size=embedding_object.num_dimensions,
                                  workers=NUM_WORKERS,
                                  iter=int(num_passes))

        # Save models
        show_progress.update_step('saving')
        model_path = os.path.join(MODELS_DIR, 'embedding', f'embedding_{str(embedding_id)}_{secrets.token_hex(10)}')
        phraser_path = os.path.join(MODELS_DIR, 'embedding', f'phraser_{str(embedding_id)}_{secrets.token_hex(10)}')
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

    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        return False


@task(name="cluster_embedding", base=BaseTask)
def cluster_embedding(clustering_id):
    # retrieve clustering object
    clustering_object = EmbeddingCluster.objects.get(pk=clustering_id)
    num_clusters = clustering_object.num_clusters
    
    task_object = clustering_object.task
    show_progress = ShowProgress(task_object, multiplier=1)

    show_progress.update_step('loading embedding')
    show_progress.update_view(0)

    try:
        embedding_id = clustering_object.embedding.pk
        embedding = W2VEmbedding(embedding_id)
        embedding.load()

        show_progress.update_step('clustering')
        show_progress.update_view(0)

        clustering = WordCluster(clustering_object.pk)
        clustering.cluster(embedding, num_clusters)

        show_progress.update_step('saving')
        show_progress.update_view(0)

        clustering_path = os.path.join(MODELS_DIR, 'embedding', f'cluster_{clustering_id}_{secrets.token_hex(10)}')
        clustering.save(clustering_path)

        # save clustering
        clustering_object.location = json.dumps({'cluster': clustering_path})
        clustering_object.save()

        # finish task
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        return True

    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise
