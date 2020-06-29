from rest_framework import status
from rest_framework.exceptions import APIException

from toolkit.helper_functions import get_core_setting
from toolkit.settings import BROKER_URL


'''
default_detail - detailed message of the exception
default_code - code identifier of exception
'''


class ProjectValidationFailed(APIException):
    ''' General class for project validation failure. If no detail argument is specified, will fall to default_detail '''
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = ("Project validation failed")
    default_code = 'validation_failed'


class NonExistantModelError(APIException):
    ''' trying to operate on a non-existant model throws this error '''
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = ("Model does not exist")
    default_code = "nonexistant_model"


class SerializerNotValid(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = ("Serializer is not valid")
    default_code = "nonvalid_serializer"


class MLPNotAvailable(APIException):
    MLP_URL = get_core_setting("TEXTA_MLP_URL")
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = (f"MLP {MLP_URL} not available. Check connection to MLP.")
    default_code = "mlp_not_available"


class RedisNotAvailable(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = (f"Redis {BROKER_URL} not available. Check connection to Redis.")
    default_code = "redis_not_available"


class InvalidInputDocument(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = ("Invalid input document")
    default_code = "invalid_document"
