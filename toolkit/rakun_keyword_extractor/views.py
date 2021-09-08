import json
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from toolkit.view_constants import BulkDelete
from .serializers import RakunExtractorSerializer, RakunExtractorRandomDocSerializer
import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.core.project.models import Project
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.elastic.index.models import Index
from toolkit.serializer_constants import GeneralTextSerializer
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import ElasticSearcher


class RakunExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RakunExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description')

    def get_queryset(self):
        return RakunExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')

    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")


        rakun: RakunExtractor = serializer.save(
            author=self.request.user,
            project=project,
            fields=json.dumps(serializer.validated_data['fields']),
            stopwords=json.dumps(serializer.validated_data.get('stopwords', []), ensure_ascii=False)
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            rakun.indices.add(index)

        rakun.apply_rakun()

    def perform_update(self, serializer: RakunExtractorSerializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        serializer.save(
            author=self.request.user,
            project=project
        )

    @action(detail=True, methods=['post'], serializer_class=RakunExtractorSerializer)
    def duplicate(self, request, pk=None, project_pk=None):
        rakun_object: RakunExtractor = self.get_object()
        rakun_object.pk = None
        rakun_object.description = f"{rakun_object.description}_copy"
        rakun_object.author = self.request.user
        rakun_object.save()

        response = {
            "message": "Rakun extractor duplicated successfully!",
            "duplicate_id": rakun_object.pk
        }

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def extract_from_text(self, request, pk=None, project_pk=None):
        serializer = GeneralTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rakun_object: RakunExtractor = self.get_object()

        text = serializer.validated_data['text']

        # apply rakun
        results = {
            "rakun_id": rakun_object.pk,
            "desscription": rakun_object.description,
            "result": False,
            "text": text,
            "keywords": []
         }
        #
        # matches = rakun_object.match_texts([text], as_texta_facts=True, field="text")
        #
        # if matches:
        #     results["result"] = True
        #     results["matches"] = matches
        return Response(results, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=RakunExtractorRandomDocSerializer)
    def extract_from_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get rakun object
        rakun_object: RakunExtractor = RakunExtractor.objects.get(pk=pk)

        serializer = RakunExtractorRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve rakun fields
        fields = serializer.validated_data["fields"]

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]
        flattened_doc = ElasticCore(check_connection=False).flatten(random_doc)

        # apply rakun
        results = {
            "rakun_id": rakun_object.pk,
            "description": rakun_object.description,
            "result": False,
            "keywords": [],
            "document": flattened_doc
        }

        # final_matches = []
        # for field in fields:
        #     text = flattened_doc.get(field, None)
        #     results["document"][field] = text
        #     matches = rakun_object.match_texts([text], as_texta_facts=True, field=field)
        #
        #     if matches:
        #         # for match in matches:
        #         # match.update(field=field)
        #         final_matches.extend(matches)
        #         results["result"] = True
        #
        # results["matches"] = final_matches
        return Response(results, status=status.HTTP_200_OK)
