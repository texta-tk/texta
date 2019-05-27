from rest_framework import viewsets, status
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



class HybridTaggerViewSet(viewsets.ModelViewSet):
    queryset = HybridTagger.objects.all()
    serializer_class = HybridTaggerSerializer


    def perform_create(self, serializer):
        serializer.save(author=self.request.user, 
                        project=self.request.user.profile.active_project)


    def create(self, request, *args, **kwargs):
        # add dummy value to tagger so serializer is happy
        request_data = request.data.copy()
        request_data.update({'tagger.description': 'dummy value'})

        # validate serializer again with updated values
        serializer = HybridTaggerSerializer(data=request_data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        tags = self.get_tags(serializer.data['fact_name'], min_count=serializer.data['minimum_sample_size'])

        self.create_queries(serializer.data['fact_name'], tags)
        
        #self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def get_tags(self, fact_name, min_count=1000):
        """
        Finds possible tags for training by aggregating active project's indices
        """
        active_indices = list(self.request.user.profile.active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(fact_name=fact_name, min_count=min_count, size=10000)
        return tag_values
    

    def create_queries(self, fact_name, tags):
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            



"""
class HybridTaggerViewSet(viewsets.ViewSet):
    ""
    Hybrid Tagger for using multiple tagger instances.
    ""
    serializer_class = HybridTaggerTextSerializer

    def _get_tagger_objects(self):
        ""
        Returns available Tagger objects for the active project.
        ""
        return Tagger.objects.filter(project=self.request.user.profile.active_project).filter(task__status='completed')


    def list(self, request):
        ""
        Lists available taggers for activated project.
        ""
        queryset = self._get_tagger_objects()
        serializer = SimpleTaggerSerializer(queryset, many=True, context={'request': request})
        return Response({'available_taggers': serializer.data})

    
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