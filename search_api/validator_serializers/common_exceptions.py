from rest_framework.exceptions import APIException


class ElasticTransportError(APIException):
    status_code = 500
    default_detail = 'Could not make Elasticsearch request.'
    default_code = 'elasticsearch_transport_error'
