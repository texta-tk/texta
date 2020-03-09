from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidIndexNameException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Inserted index name does not meet Elasticsearch rules!"
    default_code = "invalid_index_name"


class ElasticTimeoutException(APIException):
    status_code = status.HTTP_408_REQUEST_TIMEOUT
    default_detail = "Connection to Elasticsearch timed out!"
    default_code = "elasticsearch_timeout"


class ElasticTransportException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Error in Elasticsearch payload!"
    default_code = "internal_elastic_error"


class ElasticConnectionException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Error with connecting to Elasticsearch!"
    default_code = "elasticsearch_connect_error"
