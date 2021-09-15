import uuid
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from toolkit.elastic.tools.core import ElasticCore
from toolkit.tools.utils_for_tests import create_test_user, project_creation, print_output
from toolkit.test_settings import (TEST_VERSION_PREFIX, VERSION_NAMESPACE)


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):
    def setUp(self):
        self.test_index_name = f"test_apply_rakun_{uuid.uuid4().hex}"
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("RakunExtractorTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/'

        self.rakun_id = None
        self.client.login(username='user', password='pw')

        ids = []
        payloads = [
            {
                "description": "test_all",
                "distance_method": "fasttext",
                "distance_threshold": 1,
                "num_keywords": 1,
                "pair_diff_length": 1,
                "stopwords": ["word1", "word2"],
                "bigram_count_threshold": 2,
                "min_tokens": 2,
                "max_tokens": 2,
                "max_similar": 2,
                "max_occurrence": 2,
                "fasttext_embedding": 1
            },
            {
                "description": "rakun_test_new",
                "distance_method": "fasttext",
                "distance_threshold": 1.0,
                "min_tokens": 1,
                "max_tokens": 2,
                "fasttext_embedding": 1
            }
        ]

        rakun_url = reverse(f"{VERSION_NAMESPACE}:rakun_extractor-list", kwargs={"project_pk": self.project.pk})
        for payload in payloads:
            response = self.client.post(rakun_url, payload)
            self.assertTrue(response.status_code == status.HTTP_201_CREATED)
            ids.append(int(response.data["id"]))

    def tearDown(self) -> None:
        ec = ElasticCore()
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete [Rakun Extractor] test index {self.test_index_name}")

    def test(self):
        self.run_test_rakun_extractor_create()
        self.run_test_apply_rakun_extractor_to_index()

    def run_test_rakun_extractor_create(self):
        pass

    def run_test_apply_rakun_extractor_to_index(self):
        pass
