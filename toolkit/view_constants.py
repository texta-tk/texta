from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.query import Query

from toolkit.elastic.tools.feedback import Feedback
from toolkit.serializer_constants import (EmptySerializer, FeedbackSerializer, ProjectResourceBulkDeleteSerializer)


# This should only be added to views the model has the favorite removal in it.
class FavoriteModelViewMixing:


    @action(detail=True, methods=['post', ], serializer_class=EmptySerializer)
    def add_favorite(self, request, project_pk=None, pk=None):
        user = self.request.user
        orm = self.get_object()

        if orm.favorited_users.filter(pk=user.pk).exists():
            orm.favorited_users.remove(user)
            return Response({"detail": "Removed instance as a favorite!"})
        else:
            orm.favorited_users.add(user)
            return Response({"detail": "Added instance as a favorite!"})


class TagLogicViews:
    """Re-usable logic for when a view needs to deal with facts"""


    def get_tags(self, fact_name, active_project, min_count=1000, max_count=None, indices=None):
        """Finds possible tags for training by aggregating active project's indices."""
        active_indices = list(active_project.get_indices()) if indices is None else indices
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def create_queries(self, fact_name, tags):
        """Creates queries for finding documents for each tag."""
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries


class BulkDelete:
    @action(detail=False, methods=['post'], serializer_class=ProjectResourceBulkDeleteSerializer)
    def bulk_delete(self, request, project_pk=None):
        """Deletes bulk of objects, given { "ids": [int] }"""
        data = request.data
        if "ids" not in data:
            return Response({'error': 'Must include key "ids" with an array of integers (private keys)'}, status=status.HTTP_400_BAD_REQUEST)
        deleted = self.get_queryset().filter(id__in=data['ids'], project_id=project_pk).delete()
        # Show  the number of objects deleted and a dictionary with the number of deletions per object type
        info = {"num_deleted": deleted[0], "deleted_types": deleted[1]}
        return Response(info, status=status.HTTP_200_OK)


class FeedbackModelView:
    @action(detail=True, methods=['get', 'post', 'delete'], serializer_class=FeedbackSerializer)
    def feedback(self, request, project_pk=None, pk=None):
        """
        get:
        Retrieves feedback for the model.

        post:
        Adds feedback to the model.

        delete:
        Deletes feedback object for the model.
        """
        model_object = self.get_object()
        feedback = Feedback(project_pk, model_object=model_object)
        if request.method == 'POST':
            serializer = FeedbackSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            added = feedback.add(serializer.validated_data['feedback_id'], serializer.validated_data['correct_result'])
            return Response(added, status=status.HTTP_200_OK)
        elif request.method == 'DELETE':
            feedback_deleted = feedback.delete()
            return Response(feedback_deleted, status=status.HTTP_200_OK)
        elif request.method == 'GET':
            feedback_list = feedback.list()
            return Response(feedback_list, status=status.HTTP_200_OK)


class FeedbackIndexView:
    @action(detail=True, methods=['get', 'delete'])
    def feedback(self, request, pk=None):
        """
        get:
        Retrieves content for feedback index for the project

        delete:
        Deletes feedback index for the project.
        """
        feedback = Feedback(pk)
        if request.method == 'DELETE':
            feedback_deleted = feedback.delete_index()
            return Response(feedback_deleted, status=status.HTTP_200_OK)
        elif request.method == 'GET':
            feedback_list = feedback.list()
            return Response(feedback_list, status=status.HTTP_200_OK)


class AdminPermissionsViewSetMixin(object):
    ''' When admin and/or project_owners need a different serialization '''


    def get_serializer_class(self):
        current_user = self.request.user
        if current_user.is_superuser:
            return ProjectAdminSerializer
        else:
            return super(AdminPermissionsViewSetMixin, self).get_serializer_class()
