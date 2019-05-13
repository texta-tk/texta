from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import TaggerSerializer


class TaggerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows tagger models to be viewed or edited.
    """
    queryset = Tagger.objects.all()
    serializer_class = TaggerSerializer


    def get_queryset(self):
        return Tagger.objects.filter(project=self.request.user.profile.active_project)


    @staticmethod
    def get_payload(request):
        if request.GET:
            data = request.GET
        elif request.POST:
            data = request.POST
        else:
            data = {}
        return data 


    @action(detail=True, methods=['get','post'])
    def tag(self, request, pk=None):
        data = self.get_payload(request)
        print(data)
        return Response('phrased_text', status=status.HTTP_200_OK)
        #serializer = PhraserSerializer(data=data)
        #if serializer.is_valid():
        #    data = serializer.data
        #    embedding_object = self.get_object()
        #    if not embedding_object.location:
        #        return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        #    phraser = Phraser(embedding_id=embedding_object.pk)
        #    phraser.load()
        #    phrased_text = phraser.phrase(data['text'])
        #    print(data['text'])
        #    return Response(phrased_text, status=status.HTTP_200_OK)
        #else:
        #    return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)



class MultiTaggerView(GenericAPIView):
    """
    API endpoint for ...
    """
    queryset = Tagger.objects.all()
    serializer_class = TaggerSerializer

    def get_queryset(self, methods=['get','post']):
        return Tagger.objects.filter(project=self.request.user.profile.active_project)
    