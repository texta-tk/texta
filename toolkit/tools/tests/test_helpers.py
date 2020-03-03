import os

from django.test import TestCase

from toolkit.helper_functions import parse_list_env_headers


class HelperTests(TestCase):

    def test_default_list_env_application(self):
        default_val = ["http://correctone.com"]
        env = parse_list_env_headers("TEXTA_RANDOM_VAL", default_val)
        self.assertTrue(env == default_val)
        self.assertTrue(isinstance(env, list))


    def test_single_list_env_reading(self):
        env_val = "http://localhost:9200"
        default_val = ["http://correctone.com"]

        os.environ["TEXTA_SINGLE_LIST_VAL"] = env_val
        env = parse_list_env_headers("TEXTA_SINGLE_LIST_VAL", default_val)
        self.assertTrue(env == [env_val])
        self.assertTrue(isinstance(env, list))


    def test_multi_comma_separated_env_reading(self):
        env_val = "http://localhost:9200,http://localhost:4000"
        default_val = ["http://correctone.com"]

        os.environ["TEXTA_MULTIPLE_LIST_VAL"] = env_val
        env = parse_list_env_headers("TEXTA_MULTIPLE_LIST_VAL", default_val)
        self.assertTrue(isinstance(env, list))
        self.assertTrue(len(env) == 2)
        self.assertTrue(env == ["http://localhost:9200", "http://localhost:4000"])
