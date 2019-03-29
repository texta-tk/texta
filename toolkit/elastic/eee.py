from elasticsearch import Elasticsearch
import urllib
import json

#from toolkit.settings import ES_URL

ES_URL = 'http://localhost:9200'

ES_SCROLL_SIZE = 500


class ElasticCore:
    """
    Class for holding most general settings and Elasticsearch object itself
    """
    
    def __init__(self):
        self.es = Elasticsearch([ES_URL])
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
        """
        Decode mapping structure (nested dictionary) to a flat structure
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


    @staticmethod
    def encode_field_data(field):
        """
        Encodes field data into url (so it can be stored safely in Django data model)
        :result: urlencoded string
        """
        field_path = field['field']['path']
        field_type = field['field']['type']
        index = field['index']
        mapping = field['mapping']
        flat_field = {"index": index, "mapping": mapping, 
                    "field_path": field_path, "field_type": field_type}
        return urllib.parse.urlencode(flat_field)


    @staticmethod
    def decode_urfield_data(field):
        """
        Decodes urlencoded field data string into dict
        :result: field data in dict
        """
        parsed_dict = urllib.parse.parse_qs(urllib.parse.urlparse(field).path)
        parsed_dict = {a:b[0] for a,b in parsed_dict.items()}
        return parsed_dict




class ElasticSearcher:
    """
    Everything related to performing searches in Elasticsearch
    """

    def __init__(self, field_data=[], query={"query": {"match_all": {}}}, scroll_size=ES_SCROLL_SIZE, output='document'):
        """
        Output options: document (default), text (lowered & stopwords removed), sentences (text + line splitting), raw (raw elastic output)
        """
        self.field_data = self._parse_field_data(field_data)
        self.indices = ','.join([field['index'] for field in field_data])
        self.query = query
        self.scroll_size = scroll_size
        self.output = output
        self.core = ElasticCore()


    def __iter__(self):
        """
        Iterator for iterating through scroll
        """
        return self.scroll()


    @staticmethod
    def _parse_field_data(field_data):
        """
        Parses field data list into dict with index names as keys and field paths as list of strings
        """
        parsed_data = {}
        for field in field_data:
            if field['index'] not in parsed_data:
                parsed_data[field['index']] = []
            parsed_data[field['index']].append(field['field_path'])
        return parsed_data


    @staticmethod
    def doc_to_texts(doc, sentences=False):
        texts = []
        for text in doc.values():
            text = text.strip().lower()
            # remove stopwords

            if sentences == True:
                lines = text.split('\n')
                for line in lines:
                    if line:
                        texts.append(line.strip())
            else:
                texts.append(text)
        return texts


    def _parse_doc(self, doc):
        """
        Parses Elasticsearch hit into something nicer
        """
        parsed_doc = {}
        for index, field_paths in self.field_data.items():
            if doc['_index'] == index:
                for field_path in field_paths:
                    decoded_text = doc['_source']
                    for k in field_path.split('.'):
                        # get nested fields encoded as: 'field.sub_field'
                        try:
                            decoded_text = decoded_text[k]
                        except:
                            decoded_text = ""
                    if decoded_text:
                        parsed_doc[field_path] = decoded_text
        return parsed_doc


    def search(self):
        response = self.core.es.search(index=self.indices, body=self.query)
        if self.output == 'document':
            return [self._parse_doc(doc) for doc in response['hits']['hits']]
        else:
            return response


    def scroll(self):
        page = self.core.es.search(index=self.indices, body=self.query, scroll='1m', size=self.scroll_size)
        scroll_id = page['_scroll_id']
        current_page = 1

        total = page['hits']['total']
        page_size = page['hits']['total']

        while page_size > 0:
            if self.output in ['document', 'text', 'sentences']:
                for hit in page['hits']['hits']:
                    parsed_doc = self._parse_doc(hit)
                    if self.output in ['text', 'sentences']:
                        if self.output == 'sentences':
                            texts = self.doc_to_texts(parsed_doc, sentences=True)
                        else:
                            texts = self.doc_to_texts(parsed_doc)
                        for text in texts:
                            yield text
                        else:
                            yield parsed_doc
            elif self.output == 'raw':
                yield page

            # get new page
            page = self.core.es.scroll(scroll_id=scroll_id, scroll='1m')
            scroll_id = page['_scroll_id']
            page_size = len(page['hits']['hits'])
            current_page += 1



class ElasticIterator:
    """  ElasticSearch Iterator
    """

    def __init__(self, field_data, query, callback_progress=None, phraser=None):
        self.elastic = ElasticRequests(field_data=field_data, query=query)
        self.callback_progress = callback_progress
        self.phraser = phraser

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)


    def __iter__(self):
        response = self.elastic.scroll()
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



fields = [{'index': 'wikipedia_et', 'field_path': 'text_mlp.lemmas', 'field_type': 'text'}]
query = {"query": {"match_all": {}}}


for a in ElasticSearcher(field_data=fields, query=query, output='sentences'):
    a

#for a in ElasticIterator(fields, query):
#    print(a)