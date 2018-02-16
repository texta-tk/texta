from .settings import entity_reader_map, collection_reader_map, database_reader_map


class DocumentReader(object):

    @staticmethod
    def read_documents(**kwargs):
        reading_parameters = kwargs

        for format in reading_parameters['formats']:
            reader = reader_map[format]['class']
            for features in reader.get_features(**reading_parameters):
                yield features

    @staticmethod
    def count_total_documents(**kwargs):
        reading_parameters = kwargs

        total_docs = 0

        for format in reading_parameters['formats']:
            reader = reader_map[format]
            total_docs += reader.count_total_documents(**kwargs)

        return total_docs


def merge_dictionaries(*args):
    final_dictionary = {}
    for current_dictionary in args:
        for key, value in current_dictionary.items():
            final_dictionary[key] = value

    return final_dictionary


reader_map = merge_dictionaries(entity_reader_map, collection_reader_map, database_reader_map)
