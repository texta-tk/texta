from django.test import TestCase
from toolkit.elastic.core import ElasticCore
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class TestElasticCore(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.elastic_core = ElasticCore()


    def test_run(self):
        self.run_connection()
        self.run_indices()
        self.run_fields()


    def run_connection(self):
        '''Tests ElasticCore initialization.'''
        self.assertTrue(self.elastic_core.connection is True)


    def run_indices(self):
        '''Tests ElasticCore index retrieval.'''
        indices = self.elastic_core.get_indices()
        print_output('test_run_indices:indices', indices)
        self.assertTrue(isinstance(indices, list))
        self.assertTrue(TEST_INDEX in indices)


    def run_fields(self):
        '''Tests ElasticCore field operations.'''
        # test field list retrieval
        fields = self.elastic_core.get_fields()
        print_output('test_run_fields:fields', fields)
        self.assertTrue(isinstance(fields, list))
        self.assertTrue(len(fields) > 0)
        # test field data encoding
        encoded_field_data = self.elastic_core.encode_field_data(fields[0])
        print_output('test_run_fields:encoded_field_data', encoded_field_data)
        self.assertTrue(isinstance(encoded_field_data, str))
        # test field data decoding
        decoded_field_data = self.elastic_core.decode_field_data(encoded_field_data)
        print_output('test_run_fields:decoded_field_data', decoded_field_data)
        self.assertTrue(isinstance(decoded_field_data, dict))
        self.assertTrue('index' in decoded_field_data)
        self.assertTrue('mapping' in decoded_field_data)
        self.assertTrue('field_path' in decoded_field_data)
        # test field data parsing
        parsed_field_data = self.elastic_core.parse_field_data([decoded_field_data])
        print_output('test_run_fields:parsed_field_data', parsed_field_data)
        self.assertTrue(isinstance(parsed_field_data, dict))
        self.assertTrue(len(list(parsed_field_data.keys())) > 0)
