from toolkit.exceptions import InvalidInputDocument


def validate_input_document(input_document, field_data):
    # check if document exists and is a dict
    if not input_document or not isinstance(input_document, dict):
        raise InvalidInputDocument("no input document (dict) provided.")

    # check if model fields are subset of input document fields
    model_field_set = set(field_data)
    doc_field_set = set(input_document.keys())
    if not model_field_set.issubset(doc_field_set) and model_field_set != doc_field_set:
        raise InvalidInputDocument("document does not contain required fields. required fields: {}".format(field_data))

    # check if any values present in the document
    if not [v for v in input_document.values() if v]:
        raise InvalidInputDocument("no values in the input document.")

    return input_document
