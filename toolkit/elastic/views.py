from elasticsearch_dsl import Mapping
import json
import uuid

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import JsonResponse
from django_filters import rest_framework as filters
from rest_auth import views
from django.urls import reverse
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from texta_face_analyzer.face_analyzer import FaceAnalyzer

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.exceptions import ElasticIndexAlreadyExists
from toolkit.elastic.models import Index
from toolkit.elastic.serializers import (
    AddMappingToIndexSerializer,
    AddTextaFactsMapping,
    IndexSerializer,
    SnowballSerializer
)
from toolkit.permissions.project_permissions import IsSuperUser, ProjectResourceAllowed
from toolkit.tools.lemmatizer import ElasticLemmatizer
from toolkit.tools.common_utils import write_file_to_disk, delete_file
from toolkit.helper_functions import get_core_setting
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH


class FaceAnalyzerViewSet(viewsets.GenericViewSet):
    queryset = []
    serializer_class = FaceAnalyzerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed
    )


    def _save_image(self, project_id: int, pil_image):
        """
        Saves PIL image to project resources. 
        """
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(project_id) / "elastic"
        path.mkdir(parents=True, exist_ok=True)
        new_name = f"photo_{uuid.uuid4().hex}.png"
        file_path = path / new_name
        pil_image.save(file_path)
        url = reverse("protected_serve", kwargs={"project_id": project_id, "application": "elastic", "file_name": new_name})
        return {"url": url, "path": file_path}


    @action(detail=False, methods=["post"], serializer_class=AddFaceSerializer)
    def add_face(self, request, project_pk=None):
        serializer = AddFaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # get request params
        img_file = serializer.validated_data["image"]   
        index = serializer.validated_data["index"]
        name = serializer.validated_data["name"]
        value = serializer.validated_data["value"]
        # get project indices
        project_object = Project.objects.get(pk=project_pk)
        project_indices = project_object.get_indices()

        # TODO: Validate image
        # TODO: Validate elastic index name

        file_path = write_file_to_disk(img_file)

        # analyze & add photo to elastic
        face_analyzer = FaceAnalyzer(es_url=get_core_setting("TEXTA_ES_URL"), es_index=index)
        face_vectors = face_analyzer.add_photo(file_path, name=name, value=value)

        # create & add index to project if it does not exist
        if not index not in project_indices:
            index, is_open = Index.objects.get_or_create(name=index)
            project_object.indices.add(index)
            project_object.save()

        return Response({"success": f"{len(face_vectors)} face(s) added to index {index}."})
    

    def list(self, request, project_pk=None):
        return Response()


    def post(self, request, project_pk=None, serializer_class=FaceAnalyzerSerializer):
        serializer = FaceAnalyzerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # get request params
        img_file = serializer.validated_data["image"]   
        store_image = serializer.validated_data["store_image"]
        # get project indices
        project_object = Project.objects.get(pk=project_pk)
        project_indices = project_object.get_indices()
        # set working index
        if "index" in serializer.validated_data:
            index = serializer.validated_data["index"]
        else:
            index = ",".join(project_indices)

        # TODO: Validate input image

        if not project_indices:
            return Response({'error': 'No indices to use for reference!'}, status=status.HTTP_400_BAD_REQUEST)
        if index not in project_indices:
            return Response({'error': f'Index {index} not in project!'}, status=status.HTTP_400_BAD_REQUEST)
        
        # create analyzer object
        face_analyzer = FaceAnalyzer(es_url=get_core_setting("TEXTA_ES_URL"), es_index=index)
        # write file to disk
        file_path = write_file_to_disk(img_file)
        # analyze photo
        detected_faces, annotated_image = face_analyzer.analyze_photo(file_path)
        # delete original file
        delete_file(file_path)
        # reform output
        output = {
            "detected_faces": detected_faces,
            "total_detected_faces": len(detected_faces["matches"]) + len(detected_faces["no_matches"]),
            "total_matches": len(detected_faces["matches"]),
            "total_no_matches": len(detected_faces["no_matches"]),
            }
        # store annotated image
        if store_image:
            image_data = self._save_image(project_object.pk, annotated_image)
            from toolkit.settings import REST_FRAMEWORK
            output["image"] = request.build_absolute_uri(image_data["url"])
        return Response(output)


class SnowballProcessor(views.APIView):
    serializer_class = SnowballSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = SnowballSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        language = serializer.validated_data["language"]

        lemmatizer = ElasticLemmatizer(language=language)
        lemmatized = lemmatizer.lemmatize(text)

        return Response({"text": lemmatized})


class IndicesFilter(filters.FilterSet):
    id = filters.CharFilter('id', lookup_expr='exact')
    name = filters.CharFilter('name', lookup_expr='icontains')
    is_open = filters.BooleanFilter("is_open")


    class Meta:
        model = Index
        fields = []


class ElasticGetIndices(views.APIView):
    permission_classes = (IsSuperUser,)

    def get(self, request):
        """
        Returns **all** available indices from Elasticsearch.
        This is different from get_indices action in project view as it lists **all** indices in Elasticsearch.
        """
        es_core = ElasticCore()
        es_core.syncher()
        indices = [index.name for index in Index.objects.all()]
        return JsonResponse(indices, safe=False, status=status.HTTP_200_OK)


class IndexViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    queryset = Index.objects.all()
    serializer_class = IndexSerializer
    permission_classes = [IsSuperUser]

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    pagination_class = None
    filterset_class = IndicesFilter

    ordering_fields = (
        'id',
        'name',
        'is_open'
    )


    def list(self, request, *args, **kwargs):
        ec = ElasticCore()
        ec.syncher()
        response = super(IndexViewSet, self).list(request, *args, **kwargs)

        data = response.data  # Get the paginated and sorted queryset results.
        open_indices = [index for index in data if index["is_open"]]

        # Doing a stats request with no indices causes trouble.
        if open_indices:
            stats = ec.get_index_stats()

            # Update the paginated and sorted queryset results.
            for index in response.data:
                name = index["name"]
                is_open = index["is_open"]
                if is_open:
                    index.update(**stats[name])
                else:
                    # For the sake of courtesy on the front-end, make closed indices values zero.
                    index.update(size=0, doc_count=0)

        return response


    def retrieve(self, request, *args, **kwargs):
        ec = ElasticCore()
        response = super(IndexViewSet, self).retrieve(*args, *kwargs)
        if response.data["is_open"]:
            index_name = response.data["name"]
            stats = ec.get_index_stats()
            response.data.update(**stats[index_name])
        else:
            response.data.update(size=0, doc_count=0)

        return response


    def create(self, request, **kwargs):
        data = IndexSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        es = ElasticCore()
        index = data.validated_data["name"]
        is_open = data.validated_data["is_open"]

        # Using get_or_create to avoid unique name constraints on creation.
        if es.check_if_indices_exist([index]):
            # Even if the index already exists, create the index object just in case
            index, is_created = Index.objects.get_or_create(name=index)
            if is_created: index.is_open = is_open
            index.save()
            raise ElasticIndexAlreadyExists()

        else:
            index, is_created = Index.objects.get_or_create(name=index)
            if is_created: index.is_open = is_open
            index.save()

            es.create_index(index=index)
            if not is_open: es.close_index(index)
            return Response({"message": f"Added index {index} into Elasticsearch!"}, status=status.HTTP_201_CREATED)


    def destroy(self, request, pk=None, **kwargs):
        with transaction.atomic():
            index_name = Index.objects.get(pk=pk).name
            es = ElasticCore()
            es.delete_index(index_name)
            Index.objects.filter(pk=pk).delete()
            return Response({"message": f"Deleted index {index_name} from Elasticsearch!"})


    @action(detail=False, methods=['post'])
    def sync_indices(self, request, pk=None, project_pk=None):
        ElasticCore().syncher()
        return Response({"message": "Synched everything successfully!"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['patch'])
    def close_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.close_index(index.name)
        index.is_open = False
        index.save()
        return Response({"message": f"Closed the index {index.name}"})


    @action(detail=True, methods=['patch'])
    def open_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.open_index(index.name)
        if not index.is_open:
            index.is_open = True
            index.save()

        return Response({"message": f"Opened the index {index.name}"})


    @action(detail=True, methods=['post'], serializer_class=AddTextaFactsMapping)
    def add_facts_mapping(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        if index.is_open:
            es_core.add_texta_facts_mapping(index.name)
            return Response({"message": f"Added the Texta Facts mapping for: {index.name}"})
        else:
            return Response({"message": f"Index {index.name} is closed, could not add the mapping!"}, status=status.HTTP_400_BAD_REQUEST)


    # TODO Return to this part.
    @action(detail=True, methods=["post"], serializer_class=AddMappingToIndexSerializer)
    def add_mapping(self, request, pk=None, project_pk=None):
        serializer: AddMappingToIndexSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model: Index = self.get_object()
        mapping = serializer.validated_data["mappings"]

        m = Mapping(model.name)
        for field_name, elastic_type in mapping.items():
            m.field(field_name, elastic_type)

        m.save(index=model.name, using=ElasticCore().es)
        return Response(True)
