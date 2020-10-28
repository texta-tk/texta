# Create your views here.
import pathlib

from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.docparser.serializers import DocparserSerializer
from toolkit.elastic.models import Index
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH


class DocparserView(GenericAPIView):
    serializer_class = DocparserSerializer
    permission_classes = [IsAuthenticated]


    def __save_file(self, project_id: int, file_name: str, file_content: bytes):
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(project_id) / "docparser"
        path.mkdir(parents=True, exist_ok=True)
        with open(path / file_name, "wb") as fp:
            fp.write(file_content)


    def post(self, request):
        serializer: DocparserSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_id = serializer.validated_data["project_id"]
        indices = serializer.validated_data["indices"]
        file_wrapper = serializer.validated_data["file"]

        for index in indices:
            model, is_created = Index.objects.get_or_create(name=index)
            project = get_object_or_404(Project, pk=project_id)
            project.indices.add(model)

        self.__save_file(project_id, file_wrapper.name, file_wrapper.file.read())

        return Response({"detail": "Saved file into the project!"}, status=status.HTTP_200_OK)
