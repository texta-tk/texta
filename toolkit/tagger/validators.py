from rest_framework.response import Response
from rest_framework import status
from toolkit.exceptions import InvalidInputDocument

def validate_input_document(input_document, field_data):
    # check if document exists and is a dict
    if not input_document or not isinstance(input_document, dict):
        raise InvalidInputDocument("no input document (dict) provided.")

    # check if fields match
    if set(field_data) != set(input_document.keys()):
        raise InvalidInputDocument("document fields do not match. Required keys: {}".format(field_data))

    # check if any values present in the document
    if not [v for v in input_document.values() if v]:
        raise InvalidInputDocument("no values in the input document.")

    return input_document
