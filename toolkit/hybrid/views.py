from rest_framework import viewsets, status, permissions
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query

from toolkit.tagger.models import Tagger
from toolkit.hybrid.serializers import HybridTaggerSerializer
from toolkit.hybrid.models import HybridTagger
from toolkit.core import permissions as core_permissions
from toolkit import permissions as toolkit_permissions
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
        tag_values = es_a.facts(fact_name=fact_name, min_count=min_count, size=10000)
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
            



"""  
    def create(self, request):
        ""
        Run selected taggers.
        ""
        serializer = HybridTaggerTextSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        #print(request.data['taggers'])

        tagger_ids = [1,2,6]

        # apply hybrid tagger
        hybrid_tagger = HybridTagger(tagger_ids=tagger_ids)
        #hybrid_tagger.load(request.data['taggers'])
        hybrid_tagger_response = hybrid_tagger.tag_text(request.data['text'])


        return Response(hybrid_tagger_response, status=status.HTTP_200_OK)
"""