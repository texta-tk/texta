import json
import logging

from celery.decorators import task
from django.db import transaction

from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.helper_functions import apply_celery_task
from toolkit.settings import ERROR_LOGGER
from toolkit.tools.show_progress import ShowProgress
from toolkit.tools.text_processor import TextProcessor
from toolkit.topic_analyzer.clustering import ClusterContent, Clustering
from toolkit.topic_analyzer.models import Cluster, ClusteringResult
from toolkit.topic_analyzer.serializers import ClusteringSerializer
from toolkit.topic_analyzer.views import ClusteringViewSet


@task(name="start_clustering_task", base=BaseTask)
def start_clustering_task(clustering_id: int):
    clustering_obj = ClusteringResult.objects.get(pk=clustering_id)
    task_object = clustering_obj.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting clustering')
    show_progress.update_view(0)

    return clustering_id


@task(name="perform_data_clustering", base=BaseTask)
def perform_data_clustering(clustering_id):
    clustering_model = ClusteringResult.objects.get(id=clustering_id)

    try:
        serializer = ClusteringSerializer(clustering_model)

        num_clusters = serializer.data["num_cluster"]
        clustering_algorithm = serializer.data["clustering_algorithm"]
        stop_words = serializer.data["stop_words"]
        indices = clustering_model.get_indices()
        query = serializer.data["query"]
        ignored_ids = serializer.data["ignored_ids"]
        fields = serializer.data["fields"]
        display_fields = serializer.data["display_fields"]
        document_limit = serializer.data["document_limit"]
        vectorizer = serializer.data["vectorizer"]
        num_dims = serializer.data["num_dims"]
        use_lsi = serializer.data["use_lsi"]
        num_topics = serializer.data["num_topics"]

        # Removing stopwords, ignored ids while fetching the documents.
        show_progress = ShowProgress(clustering_model.task, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

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

        docs = [{"id": doc_id, "text": text} for doc_id, text in elastic_search]

        # Group em up~!
        clusters = Clustering(
            docs=docs,
            num_clusters=num_clusters,
            stop_words=stop_words,
            clustering_algorithm=clustering_algorithm,
            vectorizer=vectorizer,
            num_dims=num_dims,
            use_lsi=use_lsi,
            num_topics=num_topics
        )
        clusters.cluster()

        # Save the vector path.
        path = clustering_model.generate_name()
        clusters.save_transformation(path)

        clustering_info = {
            "pk": clustering_model.pk,
            "results": list(clusters.clustering_result.items()),
            "fields": fields,
            "indices": indices,
            "display_fields": display_fields,
            "vectors_filepath": path
        }

        return clustering_info

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        clustering_model.task.add_error(str(e))
        clustering_model.task.update_status(status=Task.STATUS_FAILED)
        clustering_model.save()
        raise e


@task(name="save_clustering_results", base=BaseTask)
def save_clustering_results(clustering_result: dict):
    with transaction.atomic():
        clustering_obj = ClusteringResult.objects.get(pk=clustering_result["pk"])
        clustering_obj.task.update_status("saving_results")

        clustering_results = clustering_result["results"]
        fields = clustering_result["fields"]
        indices = clustering_result["indices"]
        display_fields = clustering_result["display_fields"]
        vectors_filepath = clustering_result["vectors_filepath"]

        clustering_obj.vector_model.name = vectors_filepath
        clustering_obj.save()

        clusters = []
        for cluster_id, document_ids in clustering_results:
            document_ids_json = json.dumps(document_ids)

            significant_words = []
            for field in fields:
                sw = ClusteringViewSet.get_significant_words(indices, document_ids, field)
                significant_words += sw

            cluster_content = ClusterContent(document_ids, vectors_filepath=vectors_filepath)

            label = Cluster.objects.create(
                significant_words=json.dumps(significant_words),
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
    clustering_model.task.complete()
    return True


def train_cluster(obj_id: int):
    # This specific function was created to avoid annoying circular import errors.
    chain = start_clustering_task.s() | perform_data_clustering.s() | save_clustering_results.s() | finish_clustering_task.s()
    apply_celery_task(chain, obj_id)
