from celery.decorators import task
from gensim.models import word2vec

from toolkit.trainers.models import Embedding
from toolkit.settings import NUM_WORKERS

@task(name="train_embedding")
def train_embedding(embedding_id):
    embedding_object = Embedding.objects.get(pk=embedding_id)
    num_passes = 5
    # Number of word2vec passes + one pass to vocabulary building
    total_passes = num_passes + 1
    #task_params = json.loads(self.task_obj.parameters)

    #show_progress = ShowProgress(embedding_id, multiplier=1)
    #show_progress.update_step('Phraser')
    #show_progress.update_view(0)

    #sentences = EsIterator(task_params, callback_progress=show_progress)

    # build phrase model
    #phraser = Phraser(embedding_id)
    #phraser.build(sentences)

    # update progress
    #show_progress = ShowProgress(embedding_id, multiplier=total_passes)
    #show_progress.update_step('W2V')
    #show_progress.update_view(0)

    # iterate again with built phrase model to include phrases in language model
    sentences = EsIterator(task_params, callback_progress=show_progress, phraser=phraser)

    model = word2vec.Word2Vec(
        sentences,
        min_count=embedding_object.min_freq,
        size=embedding.num_dimensions,
        workers=NUM_WORKERS,
        iter=int(num_passes)
    )

    #show_progress.update_step('Cluster')
    #show_progress.update_view(100.0)

    # create cluster model
    #word_cluster = WordCluster()
    #word_cluster.cluster(model)

    # Save model
    #show_progress.update_step('Saving')

    # save model & phraser here


    # declare the job done
    #show_progress.update_step(None)
    #show_progress.update_view(100.0)

