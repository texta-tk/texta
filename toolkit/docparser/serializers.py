from rest_framework import exceptions, serializers
from rest_framework.generics import get_object_or_404

from toolkit.core.project.models import Project


class DocparserSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=0)
    file = serializers.FileField()
    indices = serializers.ListField(child=serializers.CharField(), default=[])
    file_name = serializers.CharField()


    def validate_project_id(self, value: int):
        project = get_object_or_404(Project, pk=value)
        user = self.context["request"].user
        if project.users.filter(pk=user.pk).count() != 0:
            return value
        else:
            raise exceptions.PermissionDenied(f"User '{user.username}' does not have permissions for project: {project.pk}!")
