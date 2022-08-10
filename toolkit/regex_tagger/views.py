import json
import os

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.filter_constants import FavoriteFilter
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup
from toolkit.regex_tagger.serializers import (ApplyRegexTaggerGroupSerializer, ApplyRegexTaggerSerializer, RegexGroupTaggerTagTextSerializer, RegexMultitagTextSerializer, RegexTaggerGroupMultitagDocsSerializer, RegexTaggerGroupMultitagTextSerializer, RegexTaggerGroupSerializer,
                                              RegexTaggerGroupTagDocumentSerializer, RegexTaggerSerializer, RegexTaggerTagDocsSerializer, RegexTaggerTagTextsSerializer, TagRandomDocSerializer)
from toolkit.serializer_constants import GeneralTextSerializer, ProjectResourceImportModelSerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE
from toolkit.view_constants import BulkDelete, FavoriteModelViewMixing


class RegexTaggerFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')


    class Meta:
        model = RegexTagger
        fields = []


class RegexTaggerViewSet(viewsets.ModelViewSet, BulkDelete, FavoriteModelViewMixing):
    serializer_class = RegexTaggerSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = RegexTaggerFilter
    ordering_fields = ('id', 'author__username', 'description')


    def get_queryset(self):
        queryset = RegexTagger.objects.filter(project=self.kwargs['project_pk']).order_by('-id')
        return queryset


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


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerSerializer)
    def duplicate(self, request, pk=None, project_pk=None):
        tagger_object: RegexTagger = self.get_object()
        tagger_object.pk = None
        tagger_object.description = f"{tagger_object.description}_copy"
        tagger_object.author = self.request.user
        tagger_object.save()

        response = {
            "message": "Tagger duplicated successfully!",
            "duplicate_id": tagger_object.pk
        }

        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = GeneralTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tagger_object: RegexTagger = self.get_object()

        text = serializer.validated_data['text']

        # apply tagger
        results = {
            "tagger_id": tagger_object.pk,
            "tag": tagger_object.description,
            "result": False,
            "text": text,
            "matches": []
        }

        matches = tagger_object.match_texts([text], as_texta_facts=True, field="text")

        if matches:
            results["result"] = True
            results["matches"] = matches
        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerTagTextsSerializer)
    def tag_texts(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerTagTextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tagger_object: RegexTagger = self.get_object()
        texts = serializer.validated_data['texts']

        final_results = []

        for text in texts:
            results = {
                "tagger_id": tagger_object.pk,
                "tag": tagger_object.description,
                "result": False,
                "matches": []
            }

            matches = tagger_object.match_texts([text], as_texta_facts=False)

            if matches:
                results["result"] = True
                results["matches"] = matches
            final_results.append(results)

        return Response(final_results, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'], serializer_class=RegexMultitagTextSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        serializer = RegexMultitagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # filter taggers
        project_object = Project.objects.get(id=project_pk)
        tagger_objects = RegexTagger.objects.filter(project=project_object)
        # filter again
        if serializer.validated_data['taggers']:
            regex_taggers = tagger_objects.filter(pk__in=serializer.validated_data['taggers'])
        else:
            regex_taggers = tagger_objects.all()

        text = serializer.validated_data["text"]

        result = []
        for regex_tagger in regex_taggers:
            matches = regex_tagger.match_texts([text], as_texta_facts=False)

            if matches:
                new_tag = {
                    "tagger_id": regex_tagger.id,
                    "tag": regex_tagger.description,
                    "matches": matches
                }
                result.append(new_tag)
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

        input_document = serializer.validated_data["doc"]
        fields = serializer.validated_data["fields"]

        # apply tagger
        results = {
            "tagger_id": tagger_object.pk,
            "tag": tagger_object.description,
            "result": False,
            "matches": []
        }
        final_matches = []
        for field in fields:

            flattened_doc = ElasticCore(check_connection=False).flatten(input_document)
            text = flattened_doc.get(field, None)
            matches = tagger_object.match_texts([text], as_texta_facts=False)

            if matches:
                for match in matches:
                    match.update(field=field)
                final_matches.extend(matches)
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
        fields = serializer.validated_data["fields"]

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]
        flattened_doc = ElasticCore(check_connection=False).flatten(random_doc)

        # apply tagger
        results = {
            "tagger_id": tagger_object.pk,
            "tag": tagger_object.description,
            "result": False,
            "matches": [],
            "document": flattened_doc
        }

        final_matches = []
        for field in fields:
            text = flattened_doc.get(field, None)
            results["document"][field] = text
            matches = tagger_object.match_texts([text], as_texta_facts=True, field=field)

            if matches:
                # for match in matches:
                # match.update(field=field)
                final_matches.extend(matches)
                results["result"] = True

        results["matches"] = final_matches
        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ApplyRegexTaggerSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        from toolkit.regex_tagger.tasks import apply_regex_tagger

        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object: RegexTagger = self.get_object()
            new_task = Task.objects.create(regextagger=tagger_object, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
            tagger_object.save()

            tagger_object.tasks.add(new_task)

            indices = [index["name"] for index in serializer.validated_data["indices"]]
            # indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]

            fact_name = serializer.validated_data["new_fact_name"]
            fact_value = serializer.validated_data["new_fact_value"]

            add_spans = serializer.validated_data["add_spans"]

            args = (pk, "regex_tagger", indices, fields, query, es_timeout, bulk_size, max_chunk_bytes, fact_name, fact_value, add_spans)
            transaction.on_commit(lambda: apply_regex_tagger.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying RegexTagger with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)


class RegexTaggerGroupFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')


    class Meta:
        model = RegexTaggerGroup
        fields = []


class RegexTaggerGroupViewSet(viewsets.ModelViewSet, BulkDelete, FavoriteModelViewMixing):
    serializer_class = RegexTaggerGroupSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = RegexTaggerGroupFilter
    ordering_fields = ('id', 'author__username', 'description')


    def get_queryset(self):
        return RegexTaggerGroup.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_update(self, serializer: RegexTaggerGroupSerializer):
        serializer.save()

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


    @action(detail=False, methods=['post'], serializer_class=RegexTaggerGroupMultitagDocsSerializer)
    def multitag_docs(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # filter tagger groups present in project
        project_object = Project.objects.get(id=project_pk)
        regex_taggers_groups = RegexTaggerGroup.objects.filter(project=project_object)
        # filter again based on serializer
        if serializer.validated_data['tagger_groups']:
            regex_taggers_groups = regex_taggers_groups.filter(pk__in=serializer.validated_data['tagger_groups'])

        docs = serializer.validated_data["docs"]
        fields = serializer.validated_data["fields"]

        # apply taggers
        result = []
        for regex_tagger_group in regex_taggers_groups:
            matches = regex_tagger_group.tag_docs(fields, docs)
            result.extend(matches)

        result = ElasticDocument.remove_duplicate_facts(result)

        return Response(result, status=status.HTTP_200_OK)


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

        text = serializer.validated_data["text"]
        # apply taggers
        result = []
        for regex_tagger_group in regex_taggers_groups:
            tags = []
            for regex_tagger in regex_tagger_group.regex_taggers.all():

                matches = regex_tagger.match_texts([text], as_texta_facts=False)

                if matches:
                    new_tag = {
                        "tagger_id": regex_tagger.id,
                        "tag": regex_tagger.description,
                        "matches": matches
                    }
                    tags.append(new_tag)
            if tags:
                new_tagger_group_tag = {
                    "tagger_group_id": regex_tagger_group.id,
                    "tagger_group_tag": regex_tagger_group.description,
                    "tags": tags

                }
                result.append(new_tagger_group_tag)

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
            new_task = Task.objects.create(regextaggergroup=tagger_object, task_type=Task.TYPE_APPLY, status=Task.STATUS_CREATED)
            tagger_object.save()

            tagger_object.tasks.add(new_task)

            project = Project.objects.get(pk=project_pk)
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]

            args = (pk, "regex_tagger_group", indices, fields, query, es_timeout, bulk_size, max_chunk_bytes)
            transaction.on_commit(lambda: apply_regex_tagger.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying RegexTaggerGroup with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], serializer_class=RegexGroupTaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = RegexGroupTaggerTagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # retrieve tagger object
        text = serializer.validated_data["text"]
        tagger_object: RegexTaggerGroup = self.get_object()
        matches = tagger_object.match_texts([text], as_texta_facts=True, field="text")
        result = {
            "tagger_group_id": tagger_object.id,
            "tagger_group_tag": tagger_object.description,
            "result": False,
            "text": text,
            "matches": []
        }
        if matches:
            result["result"] = True
            result["matches"] = matches

        return Response(result, status=status.HTTP_200_OK)


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
        fields = serializer.validated_data["fields"]
        if not ElasticCore().check_if_indices_exist(tagger_object.project.get_indices()):
            return Response({'error': f'One or more index from {list(tagger_object.project.get_indices())} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]
        flattened_doc = ElasticCore(check_connection=False).flatten(random_doc)

        # apply tagger
        results = {
            "tagger_group_id": tagger_object.pk,
            "tagger_group_tag": tagger_object.description,
            "result": False,
            "matches": [],
            "document": flattened_doc
        }

        final_matches = []
        for field in fields:
            text = flattened_doc.get(field, None)
            results["document"][field] = text
            matches = tagger_object.match_texts([text], as_texta_facts=True, field=field)

            if matches:
                final_matches.extend(matches)
                results["result"] = True

        results["matches"] = final_matches

        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerTagDocsSerializer)
    def tag_docs(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tagger_object: RegexTaggerGroup = self.get_object()
        docs = serializer.validated_data["docs"]
        fields = serializer.validated_data["fields"]

        results = tagger_object.tag_docs(fields, docs)

        return Response(results, status=status.HTTP_200_OK)
