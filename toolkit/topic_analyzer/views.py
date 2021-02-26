# Create your views here.
import json
import pathlib
from typing import List

import rest_framework.filters as drf_filters
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from texta_tools.embedding import Phraser
from texta_tools.text_processor import TextProcessor
from toolkit.topic_analyzer.models import Cluster, ClusteringResult
from toolkit.topic_analyzer.serializers import ClusterSerializer, ClusteringIdsSerializer, ClusteringSerializer, TransferClusterDocumentsSerializer
from .clustering import ClusterContent
from ..elastic.tools.document import ElasticDocument
from toolkit.elastic.index.models import Index
from ..elastic.tools.searcher import ElasticSearcher
from ..elastic.tools.serializers import ElasticFactSerializer, ElasticMoreLikeThisSerializer
from ..pagination import PageNumberPaginationDataOnly
from ..permissions.project_permissions import ProjectResourceAllowed
from ..settings import REST_FRAMEWORK
from ..view_constants import BulkDelete


class ClusterViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ClusterSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectResourceAllowed]

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)

    ordering_fields = (
        'id',
        'fields',
        'task__time_started',
        'task__time_completed',
        'indices__name',
        'display_fields',
        'intracluster_similarity',
        'document_count'
    )


    def get_queryset(self):
        return Cluster.objects.filter(clusteringresult__project__pk=self.kwargs["project_pk"], clusteringresult__pk=self.kwargs["clustering_pk"])


    def update(self, request, *args, **kwargs):
        serializer = ClusterSerializer(data=request.data, partial=True)
        serializer.is_valid()

        cluster = Cluster.objects.get(pk=kwargs["pk"])
        clustering_object = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])

        fields = json.loads(cluster.fields)
        stop_words = json.loads(clustering_object.stop_words)
        indices = json.loads(cluster.indices)

        if "document_ids" in serializer.validated_data:
            document_ids = serializer.validated_data["document_ids"]
            ed = ElasticDocument("*")

            # Validate that those documents exist.
            validated_docs = ed.get_bulk(document_ids)
            if validated_docs:
                unique_ids = list(set([index["_id"] for index in validated_docs]))
                cluster.document_ids = json.dumps(unique_ids)

                sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=unique_ids, stop_words=stop_words)
                cluster.significant_words = json.dumps(sw)

                cluster_content = ClusterContent(unique_ids, vectors_filepath=clustering_object.vector_model.name)
                cluster.intracluster_similarity = cluster_content.get_intracluster_similarity()
            else:
                cluster.document_ids = json.dumps([])

        cluster.save()
        return Response({"message": "Cluster has been updated successfully!"})


    def retrieve(self, request, *args, **kwargs):
        queryset = Cluster.objects.filter(clusteringresult__project__pk=self.kwargs["project_pk"], clusteringresult__pk=self.kwargs["clustering_pk"])
        cluster = get_object_or_404(queryset, pk=self.kwargs["pk"])

        doc_ids = json.loads(cluster.document_ids)
        fields = json.loads(cluster.fields)
        indices = json.loads(cluster.indices)
        significant_words = json.loads(cluster.significant_words)
        display_fields = json.loads(cluster.display_fields)

        if display_fields:
            fields += display_fields

        ed = ElasticDocument(index=",".join(indices))

        documents = ed.get_bulk(doc_ids, flatten=True)
        documents = documents if documents else []
        documents = [{"id": doc["_id"], "index": doc["_index"], "content": doc["_source"]} for doc in documents]

        formated_cluster = {"id": cluster.pk, "intracluster_similarity": cluster.intracluster_similarity, "document_count": cluster.get_document_count(), "significant_words": significant_words, "documents": documents}
        return Response(formated_cluster)


    def destroy(self, request, *args, **kwargs):
        Cluster.objects.get(pk=kwargs["pk"]).delete()
        return Response({"message": "Cluster deleted."}, status=status.HTTP_200_OK)


    @action(detail=True, methods=["post"], serializer_class=ClusteringIdsSerializer)
    def expand_cluster(self, request, *args, **kwargs):
        serializer = ClusteringIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        clustering_obj = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        current_cluster_obj = clustering_obj.cluster_result.get(pk=kwargs["pk"])
        clustering_obj_clusters = clustering_obj.cluster_result.exclude(pk=kwargs["pk"])

        indices = clustering_obj.get_indices()
        stop_words = json.loads(clustering_obj.stop_words)
        fields = json.loads(clustering_obj.fields)

        documents_for_expanding = serializer.validated_data["ids"]

        # Find which of these documents already exist in some other cluster. Remove such documents from the original cluster. Update cluster parameters.
        to_transfer_documents = []
        for cluster_obj in clustering_obj_clusters:
            cluster_documents = json.loads(cluster_obj.document_ids)
            to_transfer = [doc_id for doc_id in cluster_documents if doc_id in documents_for_expanding]

            if (len(to_transfer) > 0):
                # Remove the documents to be transferred from the original cluster.
                remaining_documents = [doc_id for doc_id in cluster_documents if doc_id not in to_transfer]
                cluster_obj.document_ids = json.dumps(remaining_documents)

                # Save the new similarity score.
                cc = ClusterContent(doc_ids=remaining_documents, vectors_filepath=clustering_obj.vector_model.path)
                cluster_obj.intracluster_similarity = float(cc.get_intracluster_similarity())

                # Edit the significant words of the cluster from which we took the documents from.
                sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=remaining_documents, stop_words=stop_words)
                cluster_obj.significant_words = json.dumps(sw)

                to_transfer_documents += to_transfer
                cluster_obj.save()

        # Find which documents are new and do not belong to any cluster.
        to_add_documents = [doc_id for doc_id in documents_for_expanding if doc_id not in to_transfer_documents]

        # Get texts of these new documents so that document vectors can be calculated for these documents.
        to_add_documents_texts = []
        phraser = None
        if (len(to_add_documents) > 0):
            document_limit = clustering_obj.document_limit
            ignored_ids = json.loads(clustering_obj.ignored_ids)
            query = {"query": {"ids": {"values": to_add_documents}}}

            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)
            elastic_search = ElasticSearcher(
                indices=indices,
                query=query,
                text_processor=text_processor,
                ignore_ids=set(ignored_ids),
                output=ElasticSearcher.OUT_TEXT_WITH_ID,
                field_data=fields,
                scroll_limit=document_limit
            )

            for doc_id, text in elastic_search:
                to_add_documents_texts.append({"id": doc_id, "text": text})

            if clustering_obj.embedding:
                phraser = Phraser(embedding_id=clustering_obj.embedding.pk)
                phraser.load()

        # Save the new list of document ids.
        cluster_documents = json.loads(current_cluster_obj.document_ids)
        expanded_ids = cluster_documents + documents_for_expanding
        current_cluster_obj.document_ids = json.dumps(expanded_ids)

        # Update the similarity score since the documents were changed.
        cc = ClusterContent(doc_ids=expanded_ids, vectors_filepath=clustering_obj.vector_model.path)
        current_cluster_obj.intracluster_similarity = float(cc.get_intracluster_similarity(new_documents=to_add_documents_texts, phraser=phraser))

        # Update the significant words since the documents were changed.
        sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=expanded_ids, stop_words=stop_words)
        current_cluster_obj.significant_words = json.dumps(sw)

        current_cluster_obj.save()
        return Response({"message": "Documents successfully added to the cluster!"})


    @action(detail=True, methods=["post"], serializer_class=TransferClusterDocumentsSerializer)
    def transfer_documents(self, request, *args, **kwargs):
        serializer = TransferClusterDocumentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        clustering_obj = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        cluster_obj = clustering_obj.cluster_result.get(pk=kwargs["pk"])

        indices = clustering_obj.get_indices()
        fields = json.loads(clustering_obj.fields)
        documents_to_transfer = serializer.validated_data["ids"]
        stop_words = json.loads(clustering_obj.stop_words)

        # Remove the documents from the initial cluster.
        saved_documents = json.loads(cluster_obj.document_ids)
        unique_ids = list(set([document for document in saved_documents if document not in documents_to_transfer]))
        cluster_obj.document_ids = json.dumps(unique_ids)

        # Save the new similarity score.
        cc = ClusterContent(doc_ids=unique_ids, vectors_filepath=clustering_obj.vector_model.path)
        cluster_obj.intracluster_similarity = float(cc.get_intracluster_similarity())

        # Edit the significant words of the cluster from which you took the documents from.
        sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=unique_ids, stop_words=stop_words)
        cluster_obj.significant_words = json.dumps(sw)

        cluster_obj.save()

        # Add the previously removed documents to the new cluster.
        cluster_for_transfer = Cluster.objects.get(pk=serializer.validated_data["receiving_cluster_id"])
        cluster_documents = json.loads(cluster_for_transfer.document_ids)
        unique_ids = list(set(cluster_documents + documents_to_transfer))
        cluster_for_transfer.document_ids = json.dumps(unique_ids)

        # Update the score.
        cc = ClusterContent(doc_ids=unique_ids, vectors_filepath=clustering_obj.vector_model.path)
        cluster_for_transfer.intracluster_similarity = float(cc.get_intracluster_similarity())

        # Edit the significant words of the cluster from which you took the documents from.
        sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=unique_ids, stop_words=stop_words)
        cluster_for_transfer.significant_words = json.dumps(sw)

        cluster_for_transfer.save()
        return Response({"message": "Documents successfully added to the cluster!"})


    @action(detail=True, methods=["post"], serializer_class=ClusteringIdsSerializer)
    def add_documents(self, request, *args, **kwargs):
        serializer = ClusteringIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        clustering_obj = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        cluster_obj = clustering_obj.cluster_result.get(pk=kwargs["pk"])
        indices = clustering_obj.get_indices()
        stop_words = json.loads(clustering_obj.stop_words)
        fields = json.loads(clustering_obj.fields)

        ed = ElasticDocument(indices)

        # Get full elasticsearch documents with id, index, type and source values.
        existing_documents: List[dict] = ed.get_bulk(serializer.validated_data["ids"])
        existing_documents: List[str] = [document["_id"] for document in existing_documents]

        saved_documents = json.loads(cluster_obj.document_ids)
        unique_ids = list(set(existing_documents + saved_documents))
        cluster_obj.document_ids = json.dumps(unique_ids)

        # get texts of new documents
        new_documents = []
        phraser = None
        new_ids = [doc_id for doc_id in unique_ids if doc_id not in saved_documents]
        if len(new_ids) > 0:
            indices = clustering_obj.get_indices()
            stop_words = json.loads(clustering_obj.stop_words)
            ignored_ids = json.loads(clustering_obj.ignored_ids)
            fields = json.loads(clustering_obj.fields)
            document_limit = clustering_obj.document_limit
            query = {"query": {"ids": {"values": new_ids}}}

            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)
            elastic_search = ElasticSearcher(
                indices=indices,
                query=query,
                text_processor=text_processor,
                ignore_ids=set(ignored_ids),
                output=ElasticSearcher.OUT_TEXT_WITH_ID,
                field_data=fields,
                scroll_limit=document_limit
            )

            for doc_id, text in elastic_search:
                new_documents.append({"id": doc_id, "text": text})

            if clustering_obj.embedding:
                phraser = Phraser(embedding_id=clustering_obj.embedding.pk)
                phraser.load()

        # Update the similarity score since the documents were changed.
        cc = ClusterContent(doc_ids=unique_ids, vectors_filepath=clustering_obj.vector_model.path)
        cluster_obj.intracluster_similarity = float(cc.get_intracluster_similarity(new_documents=new_documents, phraser=phraser))

        # Update the significant words since the documents were changed.
        sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=unique_ids, stop_words=stop_words)
        cluster_obj.significant_words = json.dumps(sw)

        cluster_obj.save()
        return Response({"message": str(len(new_ids)) + " new document(s) successfully added to the cluster!"})


    @action(detail=True, methods=["post"], serializer_class=ClusteringIdsSerializer)
    def remove_documents(self, request, *args, **kwargs):
        serializer = ClusteringIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        clustering_obj = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        cluster_obj = clustering_obj.cluster_result.get(pk=kwargs["pk"])

        # JSON fields.
        indices = clustering_obj.get_indices()
        fields = json.loads(clustering_obj.fields)
        stop_words = json.loads(clustering_obj.stop_words)

        # Edit the changed document ids, removing duplicates.
        saved_documents = json.loads(cluster_obj.document_ids)
        filtered_documents = list(set([document for document in saved_documents if document not in serializer.validated_data["ids"]]))
        cluster_obj.document_ids = json.dumps(filtered_documents)

        # Edit the similarity score bc the set of documents have been changed.
        cc = ClusterContent(doc_ids=filtered_documents, vectors_filepath=clustering_obj.vector_model.path)
        cluster_obj.intracluster_similarity = float(cc.get_intracluster_similarity())

        # Edit the significant words since the documents aren't the same anymore.
        sw = Cluster.get_significant_words(indices=indices, fields=fields, document_ids=filtered_documents, stop_words=stop_words)
        cluster_obj.significant_words = json.dumps(sw)

        cluster_obj.save()
        return Response({"message": "Documents successfully removed from the cluster!"})


    @action(detail=True, methods=["post"])
    def ignore_and_delete(self, request, *args, **kwargs):
        clustering_obj = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        cluster_obj = Cluster.objects.get(pk=kwargs["pk"])

        ignored_ids = json.loads(clustering_obj.ignored_ids)
        cluster_doc_ids = json.loads(cluster_obj.document_ids)

        unique_ids = list(set(ignored_ids + cluster_doc_ids))
        clustering_obj.ignored_ids = json.dumps(unique_ids)
        clustering_obj.save()
        cluster_obj.delete()
        return Response({"message": "Deleted cluster and added it's documents to the ignored list."}, status=status.HTTP_200_OK)


    @action(detail=True, methods=["post"], serializer_class=ElasticMoreLikeThisSerializer)
    def more_like_cluster(self, request, *args, **kwargs):
        serializer = ElasticMoreLikeThisSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        clustering_object = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        cluster = Cluster.objects.get(pk=kwargs["pk"])
        indices = clustering_object.get_indices()
        doc_ids = json.loads(cluster.document_ids)
        ignored_ids = json.loads(clustering_object.ignored_ids)

        fields = json.loads(clustering_object.fields)
        document_ids = [{"_id": doc_id} for doc_id in doc_ids]

        serializer.validated_data.pop("indices", None)
        serializer.validated_data.pop("like", None)
        serializer.validated_data.pop("fields", None)

        es = ElasticSearcher(indices=indices)
        result = es.more_like_this(indices=indices, mlt_fields=fields, like=document_ids, exclude=ignored_ids, flatten=True, **serializer.validated_data)

        return Response(result)


    @action(detail=True, methods=["post"], serializer_class=ElasticFactSerializer)
    def tag_cluster(self, request, *args, **kwargs):
        ed = ElasticDocument("_all")  # _all is special elasticsearch syntax for all indices.
        serializer = ElasticFactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cluster = Cluster.objects.get(pk=kwargs["pk"])
        clustering_object = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])
        indices = clustering_object.get_indices()

        doc_ids = json.loads(cluster.document_ids)
        ignored_ids = json.loads(clustering_object.ignored_ids)

        ed.add_fact(fact=serializer.validated_data, doc_ids=doc_ids)

        clustering_object.ignored_ids = json.dumps(doc_ids + ignored_ids)
        clustering_object.save()

        return Response({"message": f"Successfully added fact {serializer.validated_data['fact']} to the documents!"})


class ClusteringViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = ClusteringSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectResourceAllowed]

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    pagination_class = PageNumberPaginationDataOnly

    ordering_fields = (
        'id',
        'author__username',
        'description',
        'fields',
        'task__time_started',
        'task__time_completed',
        'clustering_algorithm',
        'vectorizer',
        'display_fields',
        'num_topics',
        'num_cluster',
        'num_dims',
        'document_limit',
        'indices__name',
        'task__status'
    )


    def get_queryset(self):
        return ClusteringResult.objects.filter(project=self.kwargs['project_pk'])


    def perform_update(self, serializer: ClusteringSerializer):
        with transaction.atomic():
            serializer.is_valid(raise_exception=True)
            data = {}

            # Since we don't have a solid method to handle JSON fields yet,
            # we handle those fields manually.
            if "stop_words" in serializer.validated_data:
                data["stop_words"] = json.dumps(serializer.validated_data["stop_words"])

            if "ignored_ids" in serializer.validated_data:
                data["ignored_ids"] = json.dumps(serializer.validated_data["ignored_ids"])

            if "fields" in serializer.validated_data:
                data["fields"] = json.dumps(serializer.validated_data["fields"])

            if "display_fields" in serializer.validated_data:
                data["display_fields"] = json.dumps(serializer.validated_data["display_fields"])

            if "query" in serializer.validated_data:
                data["query"] = json.dumps(serializer.validated_data["query"])

            serializer.save(**data)


    def perform_create(self, serializer):
        # Atomic transaction makes sure that when inside the context an error appears,
        # all actions within the database will be rolled back to avoid ghost records in the DB.
        with transaction.atomic():
            serializer.is_valid()

            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = serializer.validated_data["indices"]
            indices = [index["name"] for index in indices]
            indices = project.get_available_or_all_project_indices(indices)

            serializer.validated_data.pop("indices")

            clustering_result: ClusteringResult = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"]),
                display_fields=json.dumps(serializer.validated_data["display_fields"]),
                query=json.dumps(serializer.validated_data["query"]),
                stop_words=json.dumps(serializer.validated_data["stop_words"]),
                ignored_ids=json.dumps(serializer.validated_data["ignored_ids"])
            )

            clustering_result.task = Task.objects.create(clusteringresult=clustering_result)
            clustering_result.save()

            for index in Index.objects.filter(name__in=indices, is_open=True):
                clustering_result.indices.add(index)

            # Start the whole clustering process.
            clustering_result.train()


    def perform_destroy(self, instance: ClusteringResult):
        instance.cluster_result.all().delete()
        return super(ClusteringViewSet, self).perform_destroy(instance)


    @action(detail=True, methods=["post"], serializer_class=ClusteringIdsSerializer)
    def bulk_delete_clusters(self, request, *args, **kwargs):
        serializer = ClusteringIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data["ids"]
        clustering = ClusteringResult.objects.filter(pk=kwargs["pk"])
        for cluster_set in clustering:
            cluster_set.cluster_result.filter(id__in=ids).delete()

        return Response({"message": f"Deleted clusters withs ids {ids}."}, status=status.HTTP_200_OK)


    @action(detail=True, methods=["post"], serializer_class=ClusteringSerializer)
    def retrain(self, *args, **kwargs):
        clustering_obj = ClusteringResult.objects.get(pk=kwargs["pk"])
        vector_file = pathlib.Path(clustering_obj.vector_model.path)  # Delete the existing vectorfile as a new one will be generated.
        if vector_file.exists():
            vector_file.unlink()
        clustering_obj.train()
        return Response({"message": f"Started re-clustering '{clustering_obj.description}' cluster set! "})


    @action(detail=True, methods=['get'])
    def view_clusters(self, request, *args, **kwargs):
        container = []
        clustering_model = ClusteringResult.objects.get(pk=kwargs["pk"])
        clusters = clustering_model.cluster_result.all()
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")

        for cluster in clusters:
            relative_url = reverse(f"{default_version}:cluster-detail", kwargs={"pk": cluster.pk, "project_pk": kwargs["project_pk"], "clustering_pk": clustering_model.id})
            url = request.build_absolute_uri(relative_url)
            container.append(
                {
                    "id": cluster.pk,
                    "url": url,
                    "document_count": cluster.get_document_count(),
                    "average_similarity": cluster.intracluster_similarity,
                    "significant_words": json.loads(cluster.significant_words),
                    "documents": json.loads(cluster.document_ids)
                }
            )

        return Response({"cluster_count": len(container), "clusters": sorted(container, key=lambda x: x["id"], reverse=True)})
