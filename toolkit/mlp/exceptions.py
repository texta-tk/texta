from rest_framework import status
from rest_framework.exceptions import APIException


class CouldNotDetectLanguageException(APIException):
    """Raised when the input does not return a proper language code"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = ("Could not detect the language!")
    default_code = "lang_detect_failure"
