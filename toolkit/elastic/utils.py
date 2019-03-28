from toolkit.elastic.elastic import Elastic
import json

def get_field_choices():
    return [(json.dumps(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in Elastic().get_fields()]


def get_indices():
    return Elastic().get_indices()
