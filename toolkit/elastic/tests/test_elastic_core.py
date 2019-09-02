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
        print_output('test_run_fields:fields', fields[:10])
        self.assertTrue(isinstance(fields, list))
        self.assertTrue(len(fields) > 0)
