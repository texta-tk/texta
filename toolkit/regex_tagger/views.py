import json
import os

from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse

from texta_lexicon_matcher.lexicon_matcher import LexiconMatcher

from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete
from toolkit.core.project.models import Project
from .serializers import RegexTaggerSerializer, RegexTaggerTagTextsSerializer
from toolkit.serializer_constants import GeneralTextSerializer, ProjectResourceImportModelSerializer
from .models import RegexTagger


# class TaggerFilter(filters.FilterSet):
#     description = filters.CharFilter('description', lookup_expr='icontains')
#     task_status = filters.CharFilter('task__status', lookup_expr='icontains')


#     class Meta:
#         model = Tagger
#         fields = []


class RegexTaggerViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RegexTaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    #filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    #filterset_class = TaggerFilter
    #ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


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
        # load matcher
        matcher = self._load_matcher()
        # retrieve matches
        result = matcher.get_matches(serializer.validated_data['text'])
        return Response(result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=RegexTaggerTagTextsSerializer)
    def tag_texts(self, request, pk=None, project_pk=None):
        serializer = RegexTaggerTagTextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # load matcher
        matcher = self._load_matcher()
        # retrieve matches
        result = []
        for text in serializer.validated_data['texts']:
            result += matcher.get_matches(text)
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


    def _load_matcher(self):
        # retrieve tagger object
        regex_tagger_object = self.get_object()
        # parse lexicons
        lexicon = json.loads(regex_tagger_object.lexicon)
        counter_lexicon = json.loads(regex_tagger_object.counter_lexicon)
        # create matcher
        matcher = LexiconMatcher(
            lexicon,
            counter_lexicon = counter_lexicon,
            operation = regex_tagger_object.operator,
            match_type = regex_tagger_object.match_type,
            required_words = regex_tagger_object.required_words,
            phrase_slop = regex_tagger_object.phrase_slop,
            counter_slop = regex_tagger_object.counter_slop,
            return_fuzzy_match = regex_tagger_object.return_fuzzy_match
        )
        return matcher
