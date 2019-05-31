from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query

from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import TaggerSerializer, TaggerGroupSerializer, \
                                       TextSerializer, DocSerializer
from toolkit.tagger.text_tagger import TextTagger
from toolkit.utils.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions
from toolkit.core import permissions as core_permissions

import json

# initialize model cache for taggers
model_cache = ModelCache(TextTagger)


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:
        data = request.POST
    else:
        data = {}
    return data


class TaggerViewSet(viewsets.ModelViewSet):
    serializer_class = TaggerSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions,
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)

    def get_queryset(self):
        queryset = Tagger.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = Tagger.objects.filter(project=current_user.profile.active_project)
        return queryset


    def create(self, request, *args, **kwargs):
        serializer = TaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    @action(detail=True, methods=['get','post'])
    def tag_text(self, request, pk=None):
        """
        API endpoint for tagging raw text.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.data['text'], input_type='text')
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'])
    def tag_doc(self, request, pk=None):
        """
        API endpoint for tagging JSON documents.
        """
        data = get_payload(request)
        serializer = DocSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # check if fields match
        field_data = [ElasticCore().decode_field_data(field) for field in tagger_object.fields]
        field_path_list = [field['field_path'] for field in field_data]
        if field_path_list != list(serializer.validated_data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(field_path_list)}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.data['doc'], input_type='doc')
        return Response(tagger_response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_id, tagger_input, input_type='text'):
        tagger = model_cache.get_model(tagger_id)
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        return {'result': bool(tagger_result[0]), 'confidence': tagger_result[1]}


################
# TAGGER GROUP #
################


class TaggerGroupViewSet(viewsets.ModelViewSet):
    queryset = TaggerGroup.objects.all()
    serializer_class = TaggerGroupSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions,
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
        )

    def perform_create(self, serializer, tagger_set):
        serializer.save(author=self.request.user, 
                        project=self.request.user.profile.active_project,
                        taggers=tagger_set)


    def get_queryset(self):
        queryset = TaggerGroup.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = TaggerGroup.objects.filter(project=current_user.profile.active_project)
        return queryset


    def create(self, request, *args, **kwargs):
        # add dummy value to tagger so serializer is happy
        request_data = request.data.copy()
        request_data.update({'tagger.description': 'dummy value'})

        # validate serializer again with updated values
        serializer = TaggerGroupSerializer(data=request_data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # retrieve tags with sufficient counts & create queries to build models
        tags = self.get_tags(serializer.validated_data['fact_name'], min_count=serializer.validated_data['minimum_sample_size'])
        tag_queries = self.create_queries(serializer.validated_data['fact_name'], tags)
        
        # retrive tagger options from hybrid tagger serializer
        validated_tagger_data = serializer.validated_data.pop('tagger')
        validated_tagger_data.update('')

        # create tagger objects
        tagger_set = set()
        for i,tag in enumerate(tags):
            tagger_data = validated_tagger_data.copy()
            tagger_data.update({'query': json.dumps(tag_queries[i])})
            tagger_data.update({'description': tag})
            created_tagger = Tagger.objects.create(**tagger_data,
                                      author=request.user,
                                      project=self.request.user.profile.active_project)
            tagger_set.add(created_tagger)

        # create hybrid tagger object
        self.perform_create(serializer, tagger_set)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def get_tags(self, fact_name, min_count=1000):
        """
        Finds possible tags for training by aggregating active project's indices.
        """
        active_indices = list(self.request.user.profile.active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, size=10000)
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


    def get_tag_candidates(self, field_data, text):
        """
        Finds frequent tags from documents similar to input document.
        """
        es_a = ElasticAggregator()
        field_data = [es_a.core.decode_field_data(a) for a in field_data]
        es_a.update_field_data(field_data)

        field_paths = [field['field_path'] for field in field_data]

        # create & update query
        query = Query()
        query.add_mlt(field_paths, text)
        es_a.update_query(query.query)

        # perform aggregation to find frequent tags
        tag_candidates = es_a.facts(filter_by_fact_name=self.get_object().fact_name)
        return tag_candidates


    @action(detail=True, methods=['get','post'])
    def tag_text(self, request, pk=None):
        """
        API endpoint for tagging raw text with tagger group.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        hybrid_tagger_object = self.get_object()

        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status='completed'):
            return Response({'error': 'models doe not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve field data from the first element
        # we can do that safely because all taggers inside
        # hybrid tagger instance are trained on same fields
        hybrid_tagger_field_data = hybrid_tagger_object.taggers.first().fields

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(hybrid_tagger_field_data, serializer.validated_data['text'])

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, serializer.validated_data['text'], input_type='text') 

        return Response(tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'])
    def tag_doc(self, request, pk=None):
        """
        API endpoint for tagging JSON documents with tagger group.
        """
        data = get_payload(request)
        serializer = DocSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        hybrid_tagger_object = self.get_object()

        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status='completed'):
            return Response({'error': 'models doe not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve field data from the first element
        # we can do that safely because all taggers inside
        # hybrid tagger instance are trained on same fields
        hybrid_tagger_field_data = [ElasticCore().decode_field_data(field) for field in hybrid_tagger_object.taggers.first().fields]
        field_path_list = [field['field_path'] for field in hybrid_tagger_field_data]

        # check if fields match
        if field_path_list != list(serializer.validated_data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(field_path_list)}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tag candidates
        combined_texts = ' '.join(serializer.validated_data['doc'].values())
        tag_candidates = self.get_tag_candidates(hybrid_tagger_object.taggers.first().fields, combined_texts)

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, serializer.validated_data['doc'], input_type='doc')        
        return Response(tags, status=status.HTTP_200_OK)


    def apply_taggers(self, hybrid_tagger_object, tag_candidates, tagger_input, input_type='text'):
        # retrieve tagger id-s from active project
        tagger_ids = [tagger.pk for tagger in hybrid_tagger_object.taggers.filter(description__in=tag_candidates)]
        tags = []
        for tagger_id in tagger_ids:
            # apply tagger
            tagger = model_cache.get_model(tagger_id)
            if input_type == 'doc':
                tagger_result = tagger.tag_doc(tagger_input)
            else:
                tagger_result = tagger.tag_text(tagger_input)
            decision = bool(tagger_result[0])
            # if tag is omitted
            if decision:
                tagger_response = {'tag': tagger.description, 'confidence': tagger_result[1], 'tagger_id': tagger_id}
                tags.append(tagger_response)
        return tags
