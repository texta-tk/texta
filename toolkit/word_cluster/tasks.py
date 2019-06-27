from celery.decorators import task
from gensim.models import word2vec

from toolkit.embedding.models import Embedding
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.core.task.models import Task
from toolkit.word_cluster.models import WordCluster
from toolkit.word_cluster.word_cluster import WordCluster as WordClusterObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.settings import MODELS_DIR

import secrets
import json
import os


@task(name="cluster_embedding")
def cluster_embedding(clustering_id):
    # retrieve clustering object
    clustering_object = WordCluster.objects.get(pk=clustering_id)
    num_clusters = clustering_object.num_clusters
    
    task_object = clustering_object.task
    show_progress = ShowProgress(task_object, multiplier=1)

    show_progress.update_step('loading embedding')
    show_progress.update_view(0)

    embedding_id = clustering_object.embedding.pk
    embedding = W2VEmbedding(embedding_id)
    embedding.load()

    show_progress.update_step('clustering')
    show_progress.update_view(0)

    clustering = WordClusterObject(clustering_object.pk)
    clustering.cluster(embedding, num_clusters)

    show_progress.update_step('saving')
    show_progress.update_view(0)

    clustering_path = os.path.join(MODELS_DIR, 'cluster', f'cluster_{clustering_id}_{secrets.token_hex(10)}')
    clustering.save(clustering_path)

    # save clustering
    clustering_object.location = json.dumps({'cluster': clustering_path})
    clustering_object.save()

    # finish task
    show_progress.update_step('')
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
