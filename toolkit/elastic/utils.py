from toolkit.elastic.elastic import Elastic
import urllib


def field_to_urlencoded_str(field):
    field_path = field['field']['path']
    field_type = field['field']['type']
    index = field['index']
    mapping = field['mapping']
    flat_field = {"index": index, "mapping": mapping, 
                  "field_path": field_path, "field_type": field_type}
    return urllib.parse.urlencode(flat_field)


def get_field_choices():
   return [(field_to_urlencoded_str(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in Elastic().get_fields()]


def get_indices():
   return [(a, a) for a in Elastic().get_indices()]

