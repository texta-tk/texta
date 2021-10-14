from django.test import TestCase

from toolkit.core.project.models import Project
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.utils_for_tests import create_test_user


class TestSpamDetection(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('spamdetector', 'my@email.com', 'pw')
        cls.project = project_creation("spamDetector", TEST_INDEX, cls.user)
        cls.project.users.add(cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/elastic/get_spam/'


    def setUp(self):
        self.client.login(username='spamdetector', password='pw')


    def test_spam_detection(self):
        common_fields = ["client_ip", "client_cookie"]
        payload = {
            "target_field": TEST_FIELD,
            "from_date": "now-5y",
            "to_date": "now",
            "date_field": "@timestamp",
            "min_doc_count": 1,
            "common_feature_fields": common_fields
        }
        response = self.client.post(self.url, data=payload, format="json").json()
        self.assertEqual(len(response) > 1, True)

        for item in response:
            self.assertEqual({"count", "value", "co-occurances"} <= set(item), True)
            self.assertEqual(item["co-occurances"] is not None, True)
            self.assertEqual(len(item["co-occurances"]) >= 1, True)
            self.assertEqual(item["count"] >= 1, True)

            for cooccurance in item["co-occurances"]:
                self.assertEqual({"count", "value", "field"} <= set(cooccurance), True)
                self.assertEqual(cooccurance["field"] in common_fields, True)
                self.assertEqual(item["count"] >= 1, True)

