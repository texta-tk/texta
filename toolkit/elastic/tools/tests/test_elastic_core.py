import os
import unittest

import requests
from django.test import TestCase

from toolkit.settings import CORE_SETTINGS
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.exceptions import ElasticIndexNotFoundException, ElasticAuthorizationException, ElasticTransportException
from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import print_output


ES_URL = CORE_SETTINGS["TEXTA_ES_URL"]
DOCTYPE_INDEX_NAME = "test_index_two_2"
DOCTYPE_FIELD_NAME = "sample_field"
DOCTYPE_NAME = "doc"


class TestElasticXpackSecurity(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.elastic_core = ElasticCore()


    @unittest.skipIf(ElasticCore.check_for_security_xpack(), "authentication is turned on")
    def test_check_without_xpack(self):
        """
        Check whether the current mechanism works with set env values but no XPACK.
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


    def tearDown(self) -> None:
        self.elastic_core.delete_index(DOCTYPE_INDEX_NAME, ignore=[400, 404])


    def test_connection(self):
        """Tests ElasticCore initialization."""
        self.assertTrue(self.elastic_core.connection is True)


    def test_indices(self):
        """Tests ElasticCore index retrieval."""
        open_indices, closed_indices = self.elastic_core.get_indices()
        print_output("test_run_indices:indices", open_indices + closed_indices)
        self.assertTrue(isinstance(open_indices, list))
        self.assertTrue(isinstance(closed_indices, list))
        self.assertTrue(TEST_INDEX in open_indices + closed_indices)


    def test_fields(self):
        """Tests ElasticCore field operations."""
        # test field list retrieval
        fields = self.elastic_core.get_fields()
        print_output("test_run_fields:fields", fields[:10])
        self.assertTrue(isinstance(fields, list))
        self.assertTrue(len(fields) > 0)


    def test_unknown_index_exception_catching(self):
        self.assertRaises(ElasticIndexNotFoundException, self.elastic_core.get_fields, ["texta_test_index", "the_holy_hand_grenade"])


    def test_authorization_error_on_readonly_index(self):
        index_url = f"{ES_URL}/locked_index"
        create_index = requests.put(index_url)
        lock_index = requests.put(f"{index_url}/_settings", json={
            "index": {
                "blocks": {
                    "read_only_allow_delete": True
                }
            }
        })

        self.assertRaises((ElasticAuthorizationException, ElasticTransportException), self.elastic_core.create_index, "locked_index")
        requests.delete(index_url)
