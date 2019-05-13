from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import TaggerSerializer, TextSerializer, DocSerializer
from toolkit.tagger.text_tagger import TextTagger


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
    def tag_text(self, request, pk=None):
        """
        API endpoint for tagging raw text.
        """
        data = self.get_payload(request)
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
        tagger = TextTagger(tagger_object.pk)
        tagger.load()
        tagger_result = tagger.tag_text(serializer.data['text'])
        tagger_response = {"result": bool(tagger_result[0]), "confidence": tagger_result[1]}

        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'])
    def tag_doc(self, request, pk=None):
        """
        API endpoint for tagging JSON documents.
        """
        data = self.get_payload(request)
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
        if field_path_list != list(serializer.data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(field_path_list)}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger = TextTagger(tagger_object.pk)
        tagger.load()
        tagger_result = tagger.tag_doc(serializer.data['doc'])
        tagger_response = {"result": bool(tagger_result[0]), "confidence": tagger_result[1]}

        return Response(tagger_response, status=status.HTTP_200_OK)


class MultiTaggerView(GenericAPIView):
    """
    API endpoint for ...
    """
    queryset = Tagger.objects.all()
    serializer_class = TaggerSerializer

    def get_queryset(self, methods=['get','post']):
        return Tagger.objects.filter(project=self.request.user.profile.active_project)
    