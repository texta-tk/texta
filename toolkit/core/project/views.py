from django.db.models.query import QuerySet
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.core.project import permissions as project_permissions
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer, GetFactsSerializer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:
        data = request.POST
    else:
        data = {}
    return data


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (
        project_permissions.ProjectAllowed,
        permissions.IsAuthenticated
    )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


    def get_queryset(self):
        queryset = Project.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = (queryset.filter(owner=current_user) | queryset.filter(users=current_user)).distinct()
        return queryset


    @action(detail=True, methods=['get', 'post'])
    def get_fields(self, request, pk=None, project_pk=None):
        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)
        fields = ElasticCore().get_fields(indices=project_indices)
        field_map = {}
        for field in fields:
            if field['index'] not in field_map:
                field_map[field['index']] = []
            field_info = dict(field)
            del field_info['index']
            field_map[field['index']].append(field_info)
        field_map_list = [{'index': k, 'fields': v} for k,v in field_map.items()]
        return Response(field_map_list, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=GetFactsSerializer)
    def get_facts(self, request, pk=None, project_pk=None):
        data = get_payload(request)
        serializer = GetFactsSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)
        vals_per_name = serializer.validated_data['values_per_name']
        include_values = serializer.validated_data['output_type']
        fact_map = ElasticAggregator(indices=project_indices).facts(size=vals_per_name, include_values=include_values)
        fact_map_list = [{'name': k, 'values': v} for k,v in fact_map.items()]
        return Response(fact_map_list, status=status.HTTP_200_OK)
