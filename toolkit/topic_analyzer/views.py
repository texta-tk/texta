# Create your views here.
import json
import pathlib
from typing import List

from django.db import transaction
from django.urls import reverse
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.topic_analyzer.models import Cluster, ClusteringResult
from toolkit.topic_analyzer.serializers import ClusterSerializer, ClusteringSerializer
from .clustering import ClusterContent
from ..elastic.aggregator import ElasticAggregator
from ..elastic.document import ElasticDocument
from ..elastic.models import Index
from ..elastic.searcher import ElasticSearcher
from ..elastic.serializers import ElasticFactSerializer, ElasticMoreLikeThisSerializer
from ..permissions.project_permissions import ProjectResourceAllowed


class ClusterViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = ClusteringResult.objects.all()
    serializer_class = ClusterSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectResourceAllowed]


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

        fields = json.loads(clustering_object.fields)
        document_ids = [{"_id": doc_id} for doc_id in doc_ids]

        serializer.validated_data.pop("indices", None)
        serializer.validated_data.pop("like", None)
        serializer.validated_data.pop("fields", None)

        es = ElasticSearcher(indices=indices)
        result = es.more_like_this(indices=indices, mlt_fields=fields, like=document_ids, **serializer.validated_data)
        return Response(result)


    @action(detail=True, methods=["post"], serializer_class=ElasticFactSerializer)
    def tag_cluster(self, request, *args, **kwargs):
        ed = ElasticDocument("_all")  # _all is special elasticsearch syntax for all indices.
        serializer = ElasticFactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cluster = Cluster.objects.get(pk=kwargs["pk"])
        clustering_object = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])

        doc_ids = json.loads(cluster.document_ids)
        ignored_ids = json.loads(clustering_object.ignored_ids)

        ed.add_fact(fact=serializer.validated_data, doc_ids=doc_ids)

        clustering_object.ignored_ids = json.dumps(doc_ids + ignored_ids)
        clustering_object.save()

        return Response({"message": f"Successfully added fact {serializer.validated_data['fact']} to the documents!"})


    def update(self, request, *args, **kwargs):
        serializer = ClusterSerializer(data=request.data, partial=True)
        serializer.is_valid()

        cluster = Cluster.objects.get(pk=kwargs["pk"])
        clustering_object = ClusteringResult.objects.get(pk=kwargs["clustering_pk"])

        fields = json.loads(cluster.fields)
        indices = json.loads(cluster.indices)

        if "document_ids" in serializer.validated_data:
            document_ids = serializer.validated_data["document_ids"]
            ed = ElasticDocument("*")

            # Validate that those documents exist.
            validated_docs = ed.get_bulk(document_ids)
            if validated_docs:
                unique_ids = list(set([index["_id"] for index in validated_docs]))
                cluster.document_ids = json.dumps(unique_ids)
                significant_words = []
                for field in fields:
                    sw = ClusteringViewSet.get_significant_words(document_ids=unique_ids, field=field, indices=indices)
                    significant_words += sw
                cluster.significant_words = json.dumps(significant_words)

                cluster_content = ClusterContent(unique_ids, vectors_filepath=clustering_object.vector_model.name)
                cluster.intracluster_similarity = cluster_content.get_intracluster_similarity()
            else:
                cluster.document_ids = json.dumps([])

        cluster.save()
        return Response({"message": "Cluster has been updated successfully!"})


    def retrieve(self, request, *args, **kwargs):
        cluster = Cluster.objects.get(pk=kwargs["pk"])

        doc_ids = json.loads(cluster.document_ids)
        fields = json.loads(cluster.fields)
        indices = json.loads(cluster.indices)
        significant_words = json.loads(cluster.significant_words)
        original_text_field = cluster.original_text_field

        if original_text_field:
            fields.append(original_text_field)

        ed = ElasticDocument(index=",".join(indices))

        documents = ed.get_bulk(doc_ids, fields=fields)
        documents = documents if documents else []
        documents = [{"id": doc["_id"], "index": doc["_index"], "content": doc["_source"]} for doc in documents]

        formated_cluster = {"id": cluster.pk, "intracluster_similarity": cluster.intracluster_similarity, "document_count": cluster.get_document_count(), "significant_words": significant_words, "documents": documents}
        return Response(formated_cluster)


    def destroy(self, request, *args, **kwargs):
        Cluster.objects.get(pk=kwargs["pk"]).delete()
        return Response({"message": "Cluster deleted."}, status=status.HTTP_200_OK)


class ClusteringViewSet(viewsets.ModelViewSet):
    queryset = ClusteringResult.objects.all()
    serializer_class = ClusteringSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectResourceAllowed]


    @action(detail=True, methods=["put"], serializer_class=ClusteringSerializer)
    def retrain(self, *args, **kwargs):
        clustering_obj = ClusteringResult.objects.get(pk=kwargs["pk"])
        vector_file = pathlib.Path(clustering_obj.vector_model.path)  # Delete the existing vectorfile as a new one will be generated.
        if vector_file.exists(): vector_file.unlink()
        clustering_obj.train()
        return Response({"message": f"Started re-clustering '{clustering_obj.description}' cluster set! "})


    @action(detail=True, methods=['get'], serializer_class=ClusteringSerializer)
    def view_clusters(self, request, *args, **kwargs):
        container = []
        clustering_model = ClusteringResult.objects.get(pk=kwargs["pk"])
        clusters = clustering_model.cluster_result.all()

        for cluster in clusters:
            url = request.build_absolute_uri(reverse("v1:cluster-detail", kwargs={"pk": cluster.pk, "project_pk": kwargs["project_pk"], "clustering_pk": clustering_model.id}))
            container.append({"id": cluster.pk, "url": url, "document_count": cluster.get_document_count(), "average_similarity": cluster.intracluster_similarity, "documents": json.loads(cluster.document_ids)})

        return Response({"cluster_count": len(container), "clusters": container})


    @staticmethod
    def get_significant_words(indices: List[str], document_ids: List[str], field: str) -> List[dict]:
        """
        Args:
            indices: List of string to limit the indices we're looking from.
            document_ids: List of document ids to limit the range of the significant words.
            field: Path name of the field we're comparing text from for significant words.

        Returns: List of dicts with the aggregation results.

        """
        ea = ElasticAggregator(indices=indices)
        query = {'ids': {'values': document_ids}}
        sw = ea.filter_aggregation_maker(agg_type="significant_text", field=field, filter_query=query)
        sw = [{"key": hit["key"], "count": hit["doc_count"]} for hit in sw]
        return sw


    def perform_create(self, serializer):
        # Atomic transaction makes sure that when inside the context an error appears,
        # all actions within the database will be rolled back to avoid ghost records in the DB.
        with transaction.atomic():
            serializer.is_valid()

            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = serializer.validated_data["indices"]
            indices = [index["name"] for index in indices]
            indices = project.filter_from_indices(indices)

            serializer.validated_data.pop("indices")

            clustering_result: ClusteringResult = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"]),
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
