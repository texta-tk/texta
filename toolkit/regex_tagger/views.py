import json
import os

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup, load_matcher
from toolkit.regex_tagger.serializers import (
    ApplyRegexTaggerGroupSerializer, RegexGroupTaggerTagTextSerializer, RegexMultitagTextSerializer, RegexTaggerGroupMultitagTextSerializer,
    RegexTaggerGroupSerializer, RegexTaggerGroupTagDocumentSerializer, RegexTaggerSerializer,
    RegexTaggerTagTextsSerializer, TagRandomDocSerializer
)
from toolkit.serializer_constants import GeneralTextSerializer, ProjectResourceImportModelSerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE
from toolkit.view_constants import BulkDelete


c = ElasticCore()


class RegexTaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')


    class Meta:
        model = RegexTagger
        fields = []


class RegexTaggerViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RegexTaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = RegexTaggerFilter
    ordering_fields = ('id', 'author__username', 'description')


    def get_queryset(self):
        return RegexTagger.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer: RegexTaggerSerializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        serializer.save(
            author=self.request.user,
            project=project,
            lexicon=json.dumps(serializer.validated_data.get('lexicon', []), ensure_ascii=False),
            counter_lexicon=json.dumps(serializer.validated_data.get('counter_lexicon', []), ensure_ascii=False)
        )


    def perform_update(self, serializer: RegexTaggerSerializer):
        fields = ("lexicon", 'counter_lexicon')
        # Only get those parameters if they are actually in there, otherwise you will overwrite them as empty
        # when just another field is updated.
        kwargs = {field: json.dumps(serializer.validated_data.get(field), ensure_ascii=False) for field in fields if field in serializer.validated_data}
        project = Project.objects.get(id=self.kwargs['project_pk'])
        serializer.save(
            author=self.request.user,
            project=project,
            **kwargs
        )


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = GeneralTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # retrieve tagger object
        regex_tagger_object = self.get_object()
        # load matcher
        matcher = load_matcher(regex_tagger_object)
        # retrieve matches
        result = matcher.get_matches(serializer.validated_data['text'])
        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerTagTextsSerializer)
    def tag_texts(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerTagTextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regex_tagger_object: RegexTagger = self.get_object()
        matcher = load_matcher(regex_tagger_object)
        # retrieve matches
        result = []
        for text in serializer.validated_data['texts']:
            result.append(matcher.get_matches(text))
        return Response(result, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'], serializer_class=RegexMultitagTextSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        serializer = RegexMultitagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # filter taggers
        project_object = Project.objects.get(id=project_pk)
        regex_taggers = RegexTagger.objects.filter(project=project_object)
        # filter again
        if serializer.validated_data['taggers']:
            regex_taggers = regex_taggers.filter(pk__in=serializer.validated_data['taggers'])
        # apply taggers
        result = []
        for regex_tagger in regex_taggers:
            # load matcher
            matcher = load_matcher(regex_tagger)
            # retrieve matches
            matches = matcher.get_matches(serializer.validated_data['text'])
            # add tagger id and description to each match
            for match in matches:
                match["tagger_id"] = regex_tagger.id
                match["tagger_description"] = regex_tagger.description
            result += matches
        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns model as zip file."""
        zip_name = f'regex_tagger_model_{pk}.zip'
        tagger_object: RegexTagger = self.get_object()
        data = tagger_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data['file']
        tagger_id = RegexTagger.import_resources(uploaded_file, request, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model."}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerGroupTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerGroupTagDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tagger_object: RegexTagger = self.get_object()

        input_document = serializer.validated_data['doc']
        fields = serializer.validated_data["fields"]

        # apply tagger
        results = {
            "tagger_id": tagger_object.pk,
            "description": tagger_object.description,
            "result": False,
            "matches": []
        }

        final_matches = []
        for field in fields:
            flattened_doc = c.flatten(input_document)
            text = flattened_doc.get(field, None)
            matches = tagger_object.match_texts([text])
            final_matches.extend(matches)

        if final_matches:
            results["result"] = True
            results["matches"] = final_matches

        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TagRandomDocSerializer)
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get tagger object
        tagger_object: RegexTagger = RegexTagger.objects.get(pk=pk)

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve tagger fields
        tagger_fields = serializer.validated_data["fields"]

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # apply tagger
        results = {
            "tagger_id": tagger_object.pk,
            "description": tagger_object.description,
            "result": False,
            "matches": [],
            "texts": []
        }

        final_matches = []
        for field in tagger_fields:
            flattened_doc = c.flatten(random_doc)
            text = flattened_doc.get(field, None)
            if text:
                results["texts"].append(text)

            matches = tagger_object.match_texts([text])
            final_matches.extend(matches)

        if final_matches:
            results["result"] = True
            results["matches"] = final_matches

        return Response(results, status=status.HTTP_200_OK)


class RegexTaggerGroupFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')


    class Meta:
        model = RegexTaggerGroup
        fields = []


class RegexTaggerGroupViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RegexTaggerGroupSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = RegexTaggerGroupFilter
    ordering_fields = ('id', 'author__username', 'description')


    def get_queryset(self):
        return RegexTaggerGroup.objects.filter(project=self.kwargs['project_pk'])


    def perform_update(self, serializer: RegexTaggerGroupSerializer):
        super(RegexTaggerGroupViewSet, self).perform_update(serializer)

        if "regex_taggers" in serializer.validated_data:
            available_taggers = RegexTagger.objects.filter(project=self.kwargs['project_pk'])
            # Serializer contains the tagger objects but query them again since they might not have permissions
            # for them.
            tagger_ids = [tagger.pk for tagger in serializer.validated_data["regex_taggers"]]
            wished_taggers = available_taggers.filter(pk__in=tagger_ids)
            model: RegexTaggerGroup = self.get_object()
            model.regex_taggers.set(wished_taggers)


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        regex_tagger_group: RegexTaggerGroup = serializer.save(
            author=self.request.user,
            project=project,
        )
        regex_tagger_ids = [tagger.pk for tagger in serializer.validated_data['regex_taggers']]

        # retrieve taggers
        regex_taggers = RegexTagger.objects.filter(project=project.pk).filter(pk__in=regex_tagger_ids)
        regex_tagger_group.regex_taggers.set(regex_taggers)


    @action(detail=False, methods=['post'], serializer_class=RegexTaggerGroupMultitagTextSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerGroupMultitagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # filter tagger groups present in project
        project_object = Project.objects.get(id=project_pk)
        regex_taggers_groups = RegexTaggerGroup.objects.filter(project=project_object)
        # filter again based on serializer
        if serializer.validated_data['tagger_groups']:
            regex_taggers_groups = regex_taggers_groups.filter(pk__in=serializer.validated_data['tagger_groups'])
        # apply taggers
        result = []
        for regex_tagger_group in regex_taggers_groups:
            for regex_tagger in regex_tagger_group.regex_taggers.all():
                # load matcher
                matcher = load_matcher(regex_tagger)
                # retrieve matches
                matches = matcher.get_matches(serializer.validated_data['text'])
                # add tagger id and description to each match
                for match in matches:
                    match["tagger_id"] = regex_tagger.id
                    match["tagger_group_id"] = regex_tagger_group.id
                    match["tagger_description"] = regex_tagger.description
                    match["fact"] = regex_tagger_group.description
                result += matches

        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ApplyRegexTaggerGroupSerializer)
    def apply_tagger_group(self, request, pk=None, project_pk=None):
        from toolkit.regex_tagger.tasks import apply_regex_tagger

        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object: RegexTaggerGroup = self.get_object()
            tagger_object.task = Task.objects.create(regextaggergroup=tagger_object, status=Task.STATUS_CREATED)
            tagger_object.save()

            project = Project.objects.get(pk=project_pk)
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            query = serializer.validated_data["query"]

            args = (pk, indices, fields, query)
            transaction.on_commit(lambda: apply_regex_tagger.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying RegexTaggerGroup with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexGroupTaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = RegexGroupTaggerTagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # retrieve tagger object
        text = serializer.validated_data["text"]
        tagger_object: RegexTaggerGroup = self.get_object()
        matches = tagger_object.match_texts([text])
        result = {"tagger_group_id": tagger_object.id, "description": tagger_object.description, "result": False, "matches": []}
        if matches:
            result["result"] = True
            result["matches"] = matches

        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerTagTextsSerializer)
    def tag_texts(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerTagTextsSerializer(data=request.data)
        # check if valid request
        serializer.is_valid(raise_exception=True)

        # retrieve tagger object
        texts = serializer.validated_data["texts"]
        tagger_object: RegexTaggerGroup = self.get_object()
        matches = tagger_object.match_texts(texts=texts)
        result = {"tagger_group_id": tagger_object.id, "description": tagger_object.description, "result": False, "matches": []}
        if matches:
            result["result"] = True
            result["matches"] = matches

        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerGroupTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerGroupTagDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tagger_object: RegexTaggerGroup = self.get_object()

        input_document = serializer.validated_data['doc']
        fields = serializer.validated_data["fields"]

        # apply tagger
        results = {
            "tagger_group_id": tagger_object.pk,
            "description": tagger_object.description,
            "result": False,
            "matches": []
        }

        final_matches = []
        for field in fields:
            flattened_doc = c.flatten(input_document)
            text = flattened_doc.get(field, None)
            matches = tagger_object.match_texts([text])
            final_matches.extend(matches)

        if final_matches:
            results["result"] = True
            results["matches"] = final_matches

        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TagRandomDocSerializer)
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get tagger object
        tagger_object: RegexTaggerGroup = self.get_object()

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve tagger fields
        tagger_fields = serializer.validated_data["fields"]
        if not ElasticCore().check_if_indices_exist(tagger_object.project.get_indices()):
            return Response({'error': f'One or more index from {list(tagger_object.project.get_indices())} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # apply tagger
        results = {
            "tagger_group_id": tagger_object.pk,
            "description": tagger_object.description,
            "result": False,
            "matches": [],
            "texts": []
        }

        final_matches = []
        for field in tagger_fields:
            flattened_doc = c.flatten(random_doc)
            text = flattened_doc.get(field, None)
            if text:
                results["texts"].append(text)
            matches = tagger_object.match_texts([text])
            final_matches.extend(matches)

        if final_matches:
            results["result"] = True
            results["matches"] = final_matches

        return Response(results, status=status.HTTP_200_OK)
