from rest_auth import views
from rest_framework import permissions, status
from rest_framework.response import Response

from toolkit.elastic.choices import get_cluster_specific_languages
from toolkit.elastic.snowball.serializers import SnowballSerializer
from toolkit.tools.lemmatizer import ElasticLemmatizer


class SnowballProcessor(views.APIView):
    serializer_class = SnowballSerializer
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = SnowballSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        language = serializer.validated_data["language"]

        lemmatizer = ElasticLemmatizer(language=language)
        lemmatized = lemmatizer.lemmatize(text)

        return Response({"text": lemmatized})


    def get(self, request):
        languages = get_cluster_specific_languages()
        return Response(languages, status=status.HTTP_200_OK)
