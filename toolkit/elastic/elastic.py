from elasticsearch import Elasticsearch
import json

from toolkit.settings import ES_URL


class Elastic(object):
    
    def __init__(self):
        self.es = Elasticsearch([ES_URL])
        self.empty_query = json.dumps({"query": {}})
        self.connection = self._check_connection()

        self.TEXTA_RESERVED = ['texta_facts']
    
    def _check_connection(self):
        if self.es.ping():
            return True
        else:
            return False

    def get_indices(self):
        if self.connection:
            return list(self.es.indices.get_alias('*').keys())
        else:
            return []
    
    def get_fields(self):
        out = []
        if self.connection:
            for index, mappings in self.es.indices.get_mapping('*').items():
                for mapping, properties in mappings['mappings'].items():
                    properties = properties['properties']
                    for field in self._decode_mapping_structure(properties):
                        index_with_field = {'index': index, 'mapping': mapping, 'field': field}
                        out.append(index_with_field)
        return out
    

    def _decode_mapping_structure(self, structure, root_path=list(), nested_layers=list()):
        """ Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []
        for k,v in structure.items():
            # deal with fact field
            if 'properties' in v and k in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = [{'path': k, 'type': 'fact'}]
                mapping_data.extend(sub_mapping)
            # deal with object & nested structures 
            elif 'properties' in v and k not in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list)
                mapping_data.extend(sub_mapping)
            else:
                path_list = root_path[:]
                path_list.append(k)
                path = '.'.join(path_list)
                data = {'path': path, 'type': v['type']}
                mapping_data.append(data)
        return mapping_data


class ElasticIterator:
    """  ElasticSearch Iterator
    """

    def __init__(self, parameters, callback_progress=None, phraser=None):


        # self.field = json.loads(parameters['field'])['path']
        self.field = parameters['field']
        #self.es_m = ds.build_manager(ES_Manager)
        #self.es_m.load_combined_query(query)
        self.callback_progress = callback_progress
        self.phraser = phraser

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)


    def __iter__(self):
        response = self.es_m.scroll(size=ES_SCROLL_SIZE)
        scroll_id = response['_scroll_id']
        batch_hits = len(response['hits']['hits'])
        while batch_hits > 0:
            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
                raise EsIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        # get nested fields encoded as: 'field.sub_field'
                        try:
                            decoded_text = decoded_text[k]
                        except:
                            deconded_text = ""
                    
                    if decoded_text:
                        sentences = decoded_text.split('\n')
                        for sentence in sentences:
                            sentence = [word.strip().lower() for word in sentence.split(' ')]
                            sentence = STOP_WORDS.remove(sentence)
                            
                            if self.phraser:
                                sentence = self.phraser.phrase(sentence)

                            yield sentence

                except KeyError:
                    pass
                    # If the field is missing from the document
                    # Commented out logging to stop spam
                    # logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})

                except TypeError:
                    # If split failed
                    logging.getLogger(ERROR_LOGGER).error('Error splitting the text.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
            
            if self.callback_progress:
                self.callback_progress.update(batch_hits)
            
            response = self.es_m.scroll(scroll_id=scroll_id, size=ES_SCROLL_SIZE)
            batch_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

    def get_total_documents(self):
        return self.es_m.get_total_documents()