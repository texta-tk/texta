from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.tagger.models import Tagger
from toolkit.hybrid.serializers import HybridTaggerSerializer
from toolkit.hybrid.models import HybridTagger
#from toolkit.tagger.serializers import SimpleTaggerSerializer



class HybridTaggerViewSet(viewsets.ModelViewSet):
    queryset = HybridTagger.objects.all()
    serializer_class = HybridTaggerSerializer


    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)


    def create(self, request, *args, **kwargs):

        # 1. aggregate for available tags
        # 2. select fields
        # 3. build queries

        print(list(self.request.user.profile.active_project.indices))

        #Facts().get_facts()

        # update tagger data
        request_data = request.data.copy()
        request_data.update({'tagger.description': '{0}_{1}'.format(request_data['description'], request_data['fact_name'])})
        #request_data.update({'tagger.description': request_data['description']})
        # fields & query too


        serializer = HybridTaggerSerializer(data=request_data, context={'request': request})
        
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        #headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    def list(self, request):
        queryset = HybridTagger.objects.all()
        serializer = HybridTaggerSerializer(queryset, many=True, context={'request': request})
        return Response({})



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