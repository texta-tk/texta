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


class ElasticIndexNotFoundException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Could not find index!"
    default_code = "index_not_found"


class ElasticIndexAlreadyExists(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Index already exists!"
    default_code = "index_already_exists"


class ElasticAuthorizationException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Access denied to Elasticsearch!"
    default_code = "access_denied"


class ElasticAuthenticationException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentification to Elasticsearch has failed!"
    default_code = "auth_failed"


class NoIndexExists(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Index does not exist inside Elasticsearch!"
    default_code = "index_doesnt_exist"


class InvalidDataSampleError(APIException):
    """Raised on invalid Data Sample"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Class in data sample has no examples! Please check your data!"
    default_code = "no_samples"
