from rest_framework.exceptions import APIException
from rest_framework import status

'''
default_detail - detailed message of the exception
default_code - code identifier of exception
'''


class ProjectValidationFailed(APIException):
    ''' General class for project validation failure. If no detail argument is specified, will fall to default_detail '''
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Project validation failed"
    default_code = 'validation_failed'


class NonExistantModelError(APIException):
    ''' trying to operate on a non-existant model throws this error '''
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Model does not exist"
    default_code = "nonexistant_model"


class SerializerNotValid(APIException):
    pass







