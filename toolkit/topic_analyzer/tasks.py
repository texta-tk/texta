import json

from celery.decorators import task
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_tools.text_processor import TextProcessor

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE
from toolkit.tools.show_progress import ShowProgress
from toolkit.topic_analyzer.clustering import ClusterContent, Clustering
from toolkit.topic_analyzer.models import Cluster, ClusteringResult


@task(name="tag_cluster", bind=True, base=TransactionAwareTask, queue=CELERY_SHORT_TERM_TASK_QUEUE)
def tag_cluster(self, cluster_pk: int, clustering_object_pk: int, fact: dict):
    ed = ElasticDocument("")
    cluster = Cluster.objects.get(pk=cluster_pk)
    clustering_object = ClusteringResult.objects.get(pk=clustering_object_pk)
    doc_ids = json.loads(cluster.document_ids)
    ignored_ids = json.loads(clustering_object.ignored_ids)
    ed.add_fact_to_documents(fact=fact, doc_ids=doc_ids)
    clustering_object.ignored_ids = json.dumps(doc_ids + ignored_ids)
    clustering_object.save()
    return True


@task(name="start_clustering_task", base=BaseTask)
def start_clustering_task(clustering_id: int):
    clustering_obj = ClusteringResult.objects.get(pk=clustering_id)
    task_object = clustering_obj.tasks.last()
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting clustering')
    show_progress.update_view(0)

    return clustering_id


@task(name="perform_data_clustering", base=BaseTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def perform_data_clustering(clustering_id):
    clustering_model = ClusteringResult.objects.get(id=clustering_id)

    task_object = clustering_model.tasks.last()
    try:

        num_clusters = clustering_model.num_cluster
        clustering_algorithm = clustering_model.clustering_algorithm
        stop_words = json.loads(clustering_model.stop_words)
        indices = clustering_model.get_indices()
        query = json.loads(clustering_model.query)
        ignored_ids = json.loads(clustering_model.ignored_ids)
        fields = json.loads(clustering_model.fields)
        display_fields = json.loads(clustering_model.display_fields)
        document_limit = clustering_model.document_limit
        vectorizer = clustering_model.vectorizer
        num_dims = clustering_model.num_dims
        use_lsi = clustering_model.use_lsi
        num_topics = clustering_model.num_topics
        significant_words_filter = clustering_model.significant_words_filter

        # Removing stopwords, ignored ids while fetching the documents.
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        # load phraser from embedding
        if clustering_model.embedding:
            embedding = clustering_model.embedding.get_embedding()
            embedding.load_django(clustering_model.embedding)
            phraser = embedding.phraser
        else:
            phraser = None

        # Can't give parser to TextProcessor as some processing is also done in Clustering class
        text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        elastic_search = ElasticSearcher(
            indices=indices,
            query=query,
            callback_progress=show_progress,
            text_processor=text_processor,
            ignore_ids=set(ignored_ids),
            output=ElasticSearcher.OUT_TEXT_WITH_ID,
            field_data=fields,
            scroll_limit=document_limit
        )

        docs = [{"id": doc_id, "document": document} for doc_id, document in elastic_search]

        # Group em up!
        clusters = Clustering(
            docs=docs,
            num_clusters=num_clusters,
            stop_words=stop_words,
            clustering_algorithm=clustering_algorithm,
            vectorizer=vectorizer,
            num_dims=num_dims,
            use_lsi=use_lsi,
            num_topics=num_topics,
            phraser=phraser
        )
        clusters.cluster()

        # Save the vector path.
        full_vector_path, relative_vector_path = clustering_model.generate_name()
        clusters.save_transformation(full_vector_path)

        clustering_info = {
            "pk": clustering_model.pk,
            "results": list(clusters.clustering_result.items()),
            "fields": fields,
            "indices": indices,
            "display_fields": display_fields,
            "vectors_filepath": relative_vector_path,
            "stop_words": stop_words,
            "significant_words_filter": significant_words_filter
        }

        return clustering_info

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e


@task(name="save_clustering_results", base=BaseTask)
def save_clustering_results(clustering_result: dict):
    clustering_obj = ClusteringResult.objects.get(pk=clustering_result["pk"])
    task_object = clustering_obj.tasks.last()
    task_object.update_status("saving_results")

    clustering_results = clustering_result["results"]
    fields = clustering_result["fields"]
    indices = clustering_result["indices"]
    display_fields = clustering_result["display_fields"]
    vectors_filepath = clustering_result["vectors_filepath"]
    stop_words = clustering_result["stop_words"]
    significant_words_filter = clustering_result["significant_words_filter"]

    clustering_obj.vector_model.name = vectors_filepath
    clustering_obj.save()

    clusters = []
    for cluster_id, document_ids in clustering_results:
        document_ids_json = json.dumps(document_ids)

        sw = Cluster.get_significant_words(indices=indices, document_ids=document_ids, fields=fields, stop_words=stop_words, exclude=significant_words_filter)
        cluster_content = ClusterContent(document_ids, vectors_filepath=vectors_filepath)

        label = Cluster.objects.create(
            significant_words=json.dumps(sw),
            document_ids=document_ids_json,
            cluster_id=cluster_id,
            fields=json.dumps(fields),
            display_fields=json.dumps(display_fields),
            indices=json.dumps(indices),
            intracluster_similarity=cluster_content.get_intracluster_similarity()
        )

        clusters.append(label)

    # To avoid having stray clusters after retraining, we delete the previous ones,
    # and replace them with the new ones. As we don't reuse clusters it should be safe.
    if clustering_obj.cluster_result.count() == 0:
        clustering_obj.cluster_result.set(clusters)
    else:
        clustering_obj.cluster_result.all().delete()
        clustering_obj.cluster_result.set(clusters)

    return clustering_obj.id


@task(name="finish_clustering_task", base=BaseTask)
def finish_clustering_task(clustering_id: int):
    clustering_model = ClusteringResult.objects.get(id=clustering_id)
    clustering_model.tasks.last().complete()
    return True
