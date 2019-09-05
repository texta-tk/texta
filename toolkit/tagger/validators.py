from rest_framework.response import Response
from rest_framework import status

def validate_input_document(input_document, field_data):
    # check if document exists and is a dict
    if not input_document or not isinstance(input_document, dict):
        return None, Response({'error': 'no input document (dict) provided'}, status=status.HTTP_400_BAD_REQUEST)

    # check if fields match
    if set(field_data) != set(input_document.keys()):
        return None, Response({'error': 'document fields do not match. Required keys: {}'.format(field_data)}, status=status.HTTP_400_BAD_REQUEST)

    # check if any values present in the document
    if not [v for v in input_document.values() if v]:
        return None, Response({'error': 'no values in the input document.'}, status=status.HTTP_400_BAD_REQUEST)

    return input_document, None
