import logging

import elasticsearch
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from search_api.update_endpoint.update_serializers import UpdateRequestSerializer
from search_api.validator_serializers.common_exceptions import ElasticTransportError
from texta.settings import es_url, ERROR_LOGGER


class UpdateView(APIView):
    serializer_class = UpdateRequestSerializer

    def get(self, request):
        return Response()


    def post(self, request):
        serializer = UpdateRequestSerializer(data=request.data)

        # Will return an error message if not valid.
        if serializer.is_valid(raise_exception=True):
            validated_data = serializer.validated_data
            for item in validated_data["items"]:
                response = UpdateView.elastic_update_request(item)

            return Response("Editing successfull!")

    @staticmethod
    def elastic_update_request(item: dict) -> dict:
        try:
            elastic = elasticsearch.Elasticsearch(es_url)
            response = elastic.update(
                index=item["index"],
                doc_type=item["doc_type"] if "doc_type" in item else item["index"],
                id=item["id"],
                body={"doc": item["changes"]}
            )
            return response

        except elasticsearch.TransportError as e:
            # Will return the appropriate error message along with the status code.
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise ElasticTransportError(e.error)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException("There has been an unidentified error in the backend, please contact the developers about this issue.")
