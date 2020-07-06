import json
import os

from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters

from texta_lexicon_matcher.lexicon_matcher import LexiconMatcher

from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete
from toolkit.core.project.models import Project
from .serializers import (
    RegexTaggerSerializer,
    RegexTaggerTagTextsSerializer,
    RegexMultitagTextSerializer,
    RegexTaggerGroupSerializer,
    RegexTaggerGroupMultitagTextSerializer
)
from toolkit.serializer_constants import GeneralTextSerializer, ProjectResourceImportModelSerializer
from .models import RegexTagger, RegexTaggerGroup


def load_matcher(regex_tagger_object):
    # parse lexicons
    lexicon = json.loads(regex_tagger_object.lexicon)
    counter_lexicon = json.loads(regex_tagger_object.counter_lexicon)
    # create matcher
    matcher = LexiconMatcher(
        lexicon,
        counter_lexicon = counter_lexicon,
        operator = regex_tagger_object.operator,
        match_type = regex_tagger_object.match_type,
        required_words = regex_tagger_object.required_words,
        phrase_slop = regex_tagger_object.phrase_slop,
        counter_slop = regex_tagger_object.counter_slop,
        n_allowed_edits = regex_tagger_object.n_allowed_edits,
        return_fuzzy_match = regex_tagger_object.return_fuzzy_match,
        ignore_case = regex_tagger_object.ignore_case,
        ignore_punctuation = regex_tagger_object.ignore_punctuation
    )
    return matcher


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


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        tagger: RegexTagger = serializer.save(
            author=self.request.user,
            project=project,
            lexicon=json.dumps(serializer.validated_data['lexicon']),
            counter_lexicon=json.dumps(serializer.validated_data['counter_lexicon'])
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
        # retrieve tagger object
        regex_tagger_object = self.get_object()
        # load matcher
        matcher = load_matcher(regex_tagger_object)
        # retrieve matches
        result = []
        for text in serializer.validated_data['texts']:
            result += matcher.get_matches(text)
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


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        regex_tagger_group: RegexTaggerGroup = serializer.save(
            author=self.request.user,
            project=project,
        )
        regex_tagger_ids = serializer.validated_data['regex_taggers']
        # filter out incorrect id-s
        regex_tagger_ids = [_id for _id in regex_tagger_ids if RegexTagger.objects.filter(id=_id).exists()]
        # retrieve taggers
        regex_taggers = RegexTagger.objects.filter(pk__in=regex_tagger_ids)
        for regex_tagger in regex_taggers:
            regex_tagger_group.regex_taggers.add(regex_tagger)
        regex_tagger_group.save()


    @action(detail=False, methods=['post'], serializer_class=RegexTaggerGroupMultitagTextSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerGroupMultitagTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # filter tagger groups present in project
        project_object = Project.objects.get(id=project_pk)
        regex_taggers_groups = RegexTaggerGroup.objects.filter(project=project_object)
        # filter again based on serializer
        if serializer.validated_data['tagger_groups']:
            regex_taggers_groups = regex_tagger_groups.filter(pk__in=serializer.validated_data['tagger_groups'])
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
                    match["tagger_description"] = regex_tagger.description
                    match["fact"] = regex_tagger_group.description
                result += matches
        return Response(result, status=status.HTTP_200_OK)
