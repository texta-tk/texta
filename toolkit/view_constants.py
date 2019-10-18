from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.core import serializers
from django.http import HttpResponse

from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query
from toolkit.serializer_constants import ProjectResourceBulkDeleteSerializer

class TagLogicViews():
    '''Re-usable logic for when a view needs to deal with facts'''

    def get_tags(self, fact_name, active_project, min_count=1000, max_count=None):
        """
        Finds possible tags for training by aggregating active project's indices.
        """
        active_indices = list(active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def create_queries(self, fact_name, tags):
        """
        Creates queries for finding documents for each tag.
        """
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries



class BulkDelete():
    @action(detail=False, methods=['post'], serializer_class=ProjectResourceBulkDeleteSerializer)
    def bulk_delete(self, request, project_pk=None):
        '''API endpoint for bulk deleting objects, given { "ids": [int] }'''
        data = request.data
        if not "ids" in data:
            return Response({'error': 'Must include key "ids" with an array of integers (private keys)'}, status=status.HTTP_400_BAD_REQUEST)

        deleted = self.get_queryset().filter(id__in=data['ids'], project_id=project_pk).delete()
        # Show  the number of objects deleted and a dictionary with the number of deletions per object type
        info = {"num_deleted": deleted[0], "deleted_types": deleted[1] }

        return Response(info, status=status.HTTP_200_OK)

class ExportModel():
    @action(detail=True, methods=['get'])
    def export_tagger(self, request, pk=None, project_pk=None):
        """API endpoint for exporting the model."""
        # retrieve model object
        model_object = self.get_object()
        # check if model completed
        if model_object.task.status != model_object.task.STATUS_COMPLETED:
            return Response({'error': 'model is not completed'}, status=status.HTTP_400_BAD_REQUEST)
        # declare file names for the model
        zip_name = f'model_{model_object.pk}.zip'
        xml_name = f'model_{model_object.pk}.xml'
        with SpooledTemporaryFile() as tmp:
            with ZipFile(tmp, 'w', ZIP_DEFLATED) as archive:
                # write model object to zip as xml
                model_xml = serializers.serialize('xml', [model_object])
                archive.writestr(xml_name, model_xml)
                # write model files to zip
                for model_type, model_path in json.loads(model_object.location).items():
                    new_model_path = os.path.join('models', model_type, os.path.basename(model_path))
                    archive.write(model_path, arcname=new_model_path)
                # write plot files to zip
                plot_path = model_object.plot.path
                new_plot_path = os.path.join('media', os.path.basename(plot_path))
                archive.write(plot_path, arcname=new_plot_path)
            # reset file pointer
            tmp.seek(0)
            # write file data to response
            response = HttpResponse(tmp.read())
            # download file
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
            return response
        return Response()
