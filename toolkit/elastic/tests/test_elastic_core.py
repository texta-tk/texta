import os

from django.test import TestCase
from toolkit.elastic.core import ElasticCore
from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import print_output


class TestElasticCore(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.elastic_core = ElasticCore()


    def test_check_existing_auth(self):
        os.environ["TEXTA_ES_USER"] = "elastic"
        os.environ["TEXTA_ES_PASSWORD"] = "changeme"
        es = ElasticCore()
        es.es.indices.get("*")
        print_output("test_run_existing_auth", "Successfully accessed data with auth parameters in env.")


    def test_check_non_existing_auth(self):
        del os.environ["TEXTA_ES_USER"]
        del os.environ["TEXTA_ES_PASSWORD"]
        es = ElasticCore()
        es.es.indices.get("*")
        print_output("test_run_non_existing_auth", "Successfully accessed data without auth.")


    def test_connection(self):
        '''Tests ElasticCore initialization.'''
        self.assertTrue(self.elastic_core.connection is True)


    def test_indices(self):
        '''Tests ElasticCore index retrieval.'''
        indices = self.elastic_core.get_indices()
        print_output('test_run_indices:indices', indices)
        self.assertTrue(isinstance(indices, list))
        self.assertTrue(TEST_INDEX in indices)


    def test_fields(self):
        '''Tests ElasticCore field operations.'''
        # test field list retrieval
        fields = self.elastic_core.get_fields()
        print_output('test_run_fields:fields', fields[:10])
        self.assertTrue(isinstance(fields, list))
        self.assertTrue(len(fields) > 0)
