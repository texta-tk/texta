import uuid
import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.core.task.models import Task
#from toolkit.elastic.reindexer.models import Reindexer
#from toolkit.elastic.tools.aggregator import ElasticAggregator
#from toolkit.elastic.tools.core import ElasticCore
from toolkit.helper_functions import reindex_test_dataset
#from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.crf_extractor.models import CRFExtractor
from toolkit.test_settings import (
    CRF_TEST_FIELD,
    CRF_TEST_FIELD_CHOICE,
    TEST_KEEP_PLOT_FILES,
    TEST_MATCH_TEXT,
    TEST_QUERY,
    TEST_VERSION_PREFIX,
    VERSION_NAMESPACE,
    CRF_TEST_INDEX
)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class CRFExtractorViewTests(APITransactionTestCase):

    def setUp(self):
        self.test_index_name = CRF_TEST_INDEX
        self.user = create_test_user('crfOwner', 'my@email.com', 'pw')
        self.project = project_creation("crfTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/crf_extractors/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'

        self.test_crf_ids = []
        self.client.login(username='crfOwner', password='pw')


    def add_cleanup_files(self, id):
        crf = CRFExtractor.objects.get(pk=id)
        self.addCleanup(remove_file, crf.model.path)
        #if not TEST_KEEP_PLOT_FILES:
        #    self.addCleanup(remove_file, crf.plot.path)
        #if tagger_object.embedding:
        #    self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def test_run(self):
        self.run_create_crf_training_and_task_signal()

    def run_create_crf_training_and_task_signal(self):
        payload = {
                    "description": "TestCRF",
                    #"query": json.dumps(EMTPY_QUERY),
                    "test_size": 0.2,
                    "feature_fields": ["lemmas", "pos_tags"],
                    "feature_context_fields": ["lemmas", "pos_tags"],
                    "field": CRF_TEST_FIELD,
                    "indices": [{"name": self.test_index_name}],
        }

        # procees to analyze result
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_training_and_task_signal:response.data', response.data)

        # Check if Extractor gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = CRFExtractor.objects.get(id=response.data['id'])
        # add to be tested
        self.test_crf_ids.append(created.pk)
        # Check if not errors
        self.assertEqual(created.task.errors, '[]')
        # Remove tagger files after test is done
        self.add_cleanup_files(created.id)
        # Check if Task gets created via a signal
        self.assertTrue(created.task is not None)
        # Check if gets trained and completed
        self.assertEqual(created.task.status, Task.STATUS_COMPLETED)
