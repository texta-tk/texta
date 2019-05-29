from rest_framework import viewsets, status, permissions
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

#from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query

from toolkit.tagger.serializers import TextSerializer
from toolkit.tagger.models import Tagger
from toolkit.hybrid.serializers import HybridTaggerSerializer
from toolkit.hybrid.models import HybridTagger
from toolkit.core import permissions as core_permissions
from toolkit import permissions as toolkit_permissions
from toolkit.tagger.text_tagger import TextTagger

import json



class HybridTaggerViewSet(viewsets.ModelViewSet):
    queryset = HybridTagger.objects.all()
    serializer_class = HybridTaggerSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions,
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
        )

    def perform_create(self, serializer, tagger_set):
        serializer.save(author=self.request.user, 
                        project=self.request.user.profile.active_project,
                        taggers=tagger_set)


    def create(self, request, *args, **kwargs):
        # add dummy value to tagger so serializer is happy
        request_data = request.data.copy()
        request_data.update({'tagger.description': 'dummy value'})

        # validate serializer again with updated values
        serializer = HybridTaggerSerializer(data=request_data, context={'request': request})
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


    @staticmethod
    def get_payload(request):
        if request.GET:
            data = request.GET
        elif request.POST:
            data = request.POST
        else:
            data = {}
        return data


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
        API endpoint for tagging raw text.
        """
        data = self.get_payload(request)
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

        # retrieve tagger id-s from active project
        tagger_ids = [tagger.pk for tagger in Tagger.objects.filter(project=self.request.user.profile.active_project).filter(description__in=tag_candidates)]

        tags = []

        for tagger_id in tagger_ids:
            # apply tagger
            tagger = TextTagger(tagger_id)
            tagger.load()
            tagger_result = tagger.tag_text(serializer.validated_data['text'])
            decision = bool(tagger_result[0])

            # if tag is omitted
            if decision:
                tagger_response = {"tag": tagger.description, "confidence": tagger_result[1]}
                tags.append(tagger_response)

        return Response(tags, status=status.HTTP_200_OK)
