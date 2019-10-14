import os
import unittest

from django.test import TestCase

from toolkit.elastic.core import ElasticCore
from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import print_output


class TestElasticXpackSecurity(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.elastic_core = ElasticCore()

    @unittest.skipIf(ElasticCore.check_for_security_xpack(), "authentication is turned on")
    def test_check_without_xpack(self):
        """
        Check whether the current mechanism works with set env values but no XPACK.
        :return:
        """
        es = ElasticCore()
        es.es.indices.get("*")
        print_output("test_run_existing_auth", "Successfully accessed data with auth parameters in env.")

    @unittest.skipUnless(ElasticCore.check_for_security_xpack(), "authentification exists")
    def test_whether_auth_works_with_xpack(self):
        es = ElasticCore()
        es.es.indices.get("*")
        print_output("test_run_existing_auth", "Successfully accessed data with XPACK enabled.")

    @unittest.skipIf(ElasticCore.check_for_security_xpack(), "authentication is turned on")
    def test_whether_auth_works_with_no_env_values_and_no_xpack(self):
        try:
            del os.environ["TEXTA_ES_USER"]
            del os.environ["TEXTA_ES_PASSWORD"]
        except Exception:
            pass

        es = ElasticCore()
        es.es.indices.get("*")
        print_output("test_run_existing_auth", "Successfully accessed data with no env values.")


class TestElasticCore(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.elastic_core = ElasticCore()

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
