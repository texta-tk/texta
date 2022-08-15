from uuid import uuid4

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.dataset_import.models import DatasetImport
from toolkit.elastic.index.models import Index
from toolkit.test_settings import TEST_DATASETS, TEST_IMPORT_DATASET, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class DatasetImportViewTests(APITransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.user = create_test_user('Owner', 'my@email.com', 'pw')
        self.project = project_creation("testImportDatasetProject", None, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/dataset_imports/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.created_indices = []
        self.client.login(username='Owner', password='pw')


    def test_import_dataset(self):

        """Tests the endpoint for importing dataset."""
        for i, file_path in enumerate(TEST_DATASETS):
            index_name = f"{TEST_IMPORT_DATASET}-{uuid4().hex}"
            with open(file_path, 'rb') as fh:
                payload = {
                    "description": "Testimport",
                    "file": fh,
                    "index": index_name
                }
                response = self.client.post(self.url, payload)
                print_output('test_import_dataset:response.data', response.data)
                # Check if DatasetImport gets created
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                import_id = response.data['id']
                import_url = response.data['url']

                # Test that usernames are added automatically into the newly created index.
                index = Index.objects.filter(name=index_name)
                self.assertTrue(index.count() == 1)
                self.assertTrue(index.last().added_by == self.user.username)

                import_dataset = DatasetImport.objects.get(pk=import_id)
                self.created_indices.append(import_dataset.index)
                self.addCleanup(remove_file, import_dataset.file.name)
                # Check if Import is completed
                task_object = import_dataset.tasks.last()
                self.assertEqual(task_object.status, Task.STATUS_COMPLETED)
                self.assertTrue(import_dataset.num_documents > 0)
                self.assertTrue(import_dataset.num_documents_success > 0)
                self.assertTrue(import_dataset.num_documents_success <= import_dataset.num_documents)
                # Check if new index added to project
                self.assertTrue(import_dataset.index in import_dataset.project.get_indices())
                # test delete
                response = self.client.delete(import_url)
                self.assertTrue(response.status_code == status.HTTP_204_NO_CONTENT)


    def test_elasticsearch_index_name_validation(self):
        file_path = TEST_DATASETS[0]
        index_names = ["_start", "UPPERCASE_INDEX", "wild*_index", "colon:index"]
        with open(file_path, 'rb') as fh:
            for index in index_names:
                payload = {
                    "description": "Testimport",
                    "file": fh,
                    "index": index
                }
                response = self.client.post(self.url, payload)
                print_output('test_import_dataset:response.data', response.data)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_unauthenticated_dataset_import(self):
        self.client.logout()
        file_path = TEST_DATASETS[0]
        with open(file_path, 'rb') as fh:
            payload = {
                "description": "Testimport",
                "file": fh,
                "index": "test_dataset_import_unauthenticated"
            }
            response = self.client.post(self.url, data=payload, format="json")
        print_output("test_unauthenticated_dataset_import:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def tearDown(self):
        # delete created indices
        ec = ElasticCore()
        for index in self.created_indices:
            delete_response = ec.delete_index(index)
            print_output("Remove index:response", delete_response)
