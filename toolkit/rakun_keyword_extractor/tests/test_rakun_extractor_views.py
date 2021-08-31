from django.test import override_settings
from rest_framework.test import APITransactionTestCase


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):
    def setUp(self):
        pass

    def tearDown(self) -> None:
        pass

    def test(self):
        pass

    def run_test_rakun_extractor_create(self):
        pass

    def run_test_apply_rakun_extractor_to_index(self):
        pass
