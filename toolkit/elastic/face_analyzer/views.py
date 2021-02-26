from elasticsearch_dsl import Mapping
import pathlib
import uuid

import rest_framework.filters as drf_filters
from django.urls import reverse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from texta_face_analyzer.face_analyzer import FaceAnalyzer

from .serializers import FaceAnalyzerSerializer, AddFaceSerializer
from toolkit.elastic.decorators import elastic_connection
from toolkit.core.project.models import Project
from toolkit.elastic.tools.core import ElasticCore
from toolkit.permissions.project_permissions import IsSuperUser, ProjectResourceAllowed
from toolkit.tools.common_utils import write_file_to_disk, delete_file
from toolkit.helper_functions import get_core_setting
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH


@elastic_connection
def create_analyzer_object(index):
    """
    Wrapper to check Elastic connection on init.
    """
    es_core = ElasticCore()
    return FaceAnalyzer(es_object=es_core.es, es_index=index)


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
        # write file to disk
        file_path = write_file_to_disk(img_file)
        # analyze & add photo to elastic
        face_analyzer = create_analyzer_object(index)
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
        # check if indices exist and are correct
        if not project_indices:
            return Response({'error': 'No indices to use for reference!'}, status=status.HTTP_400_BAD_REQUEST)
        if index not in project_indices:
            return Response({'error': f'Index {index} not in project!'}, status=status.HTTP_400_BAD_REQUEST)
        # create analyzer object
        face_analyzer = create_analyzer_object(index)
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
