from io import StringIO
import json
import os

from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import TEST_DATASETS, TEST_IMPORT_DATASET
from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.dataset_import.models import DatasetImport
from toolkit.core.task.models import Task
from toolkit.elastic.core import ElasticCore

class DatasetImportViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('Owner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='testImportDatasetProject',
            owner=cls.user
        )
        cls.url = f'/projects/{cls.project.id}/dataset_imports/'
        cls.project_url = f'/projects/{cls.project.id}'
        cls.created_indices = []

    def setUp(self):
        self.client.login(username='Owner', password='pw')


    def test_import_dataset(self):
        """Tests the endpoint for importing dataset."""
        for file_path in TEST_DATASETS:
            with open(file_path, 'r', encoding='latin1') as fh:
                payload = {
                    "description": "Testimport",
                    "file": fh,
                    "index": TEST_IMPORT_DATASET
                }
                response = self.client.post(self.url, payload)
                print_output('test_import_dataset:response.data', response.data)
                # Check if DatasetImport gets created
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                import_id = response.data['id']
                import_dataset = DatasetImport.objects.get(pk=import_id)
                self.created_indices.append(import_dataset.index)
                self.addCleanup(remove_file, import_dataset.file.name)
                # Check if Import is completed
                self.assertEqual(import_dataset.task.status, Task.STATUS_COMPLETED)

    def tearDown(self):
        # delete created indices
        for index in self.created_indices:
            delete_response = ElasticCore().delete_index(index)
            print_output("Remove index:response", delete_response)
