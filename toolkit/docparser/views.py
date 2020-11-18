# Create your views here.
import pathlib

from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.docparser.serializers import DocparserSerializer
from toolkit.elastic.models import Index
from toolkit.helper_functions import hash_file
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH


class DocparserView(GenericAPIView):
    serializer_class = DocparserSerializer
    permission_classes = [IsAuthenticated]


    def __save_file(self, project_id: int, file_content: bytes, new_name: str):
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(project_id) / "docparser"
        path.mkdir(parents=True, exist_ok=True)

        with open(path / new_name, "wb") as fp:
            fp.write(file_content)


    def post(self, request):
        serializer: DocparserSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_id = serializer.validated_data["project_id"]
        indices = serializer.validated_data.get("indices", [])
        file_wrapper = serializer.validated_data["file"]
        content = file_wrapper.file.read()
        project = get_object_or_404(Project, pk=project_id)

        extension = pathlib.Path(file_wrapper.name).suffix
        file_hash = hash_file(file_wrapper.file)
        new_name = file_hash + extension

        for index in indices:
            model, is_created = Index.objects.get_or_create(name=index)
            project.indices.add(model)

        self.__save_file(project_id, content, new_name)

        return Response({"detail": "Saved file into the project!"}, status=status.HTTP_200_OK)
