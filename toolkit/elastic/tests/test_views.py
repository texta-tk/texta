import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_INDEX_REINDEX
from toolkit.core.project.models import Project
from toolkit.elastic.models import Reindexer
from toolkit.elastic.core import ElasticCore
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file



class ReindexerViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('indexOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='ReindexerTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        # many indices
        # cls.project_many_indices = Project.objects.create(
        #     title='ReindexerManyIndicesTestProject',
        #     owner=cls.user,
        #     indices=['texta_test_index', 'test_deletes']
        # )

        cls.project_no_indices = Project.objects.create(
            title='ReindexerNoIndicesTestProject',
            owner=cls.user
            # either has no indices or those not contained in test_payload "indices"
        )
        # cls.project_missing_fields = Project.objects.create(
        #     title='ReindexerMissingFieldsTestProject',
        #     owner=cls.user,
        #     indices=TEST_INDEX
        # )

    def setUp(self):
        self.client.login(username='indexOwner', password='pw')

    def test_run(self):
        for project in (self.project,
                        # self.project_many_indices,
                        self.project_no_indices,
                        # self.project_missing_fields,
                        ):
            url =  f'/projects/{project.id}/reindexer/'
            self.run_create_reindexer_task_signal(project, url)

    def run_create_reindexer_task_signal(self, project, url, overwrite=False):
        ''' Tests the endpoint for a new Reindexer task, and if a new Task gets created via the signal
           checks if new_index was removed '''
        payload = {
            "description": "TestReindexer",
            "fields": [TEST_FIELD],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX
        }
        # ElasticCore().delete_index(TEST_INDEX_REINDEX)
        if overwrite == False and TEST_INDEX_REINDEX not in ElasticCore().get_indices():
            response = self.client.post(url, payload, format='json')
            print_output('run_create_reindexer_task_signal:response.data', response.data)
            self.is_new_index_created_if_yes_remove(response, payload, project)
        assert TEST_INDEX_REINDEX not in ElasticCore().get_indices()
        self.is_reindexed_index_added_to_project(response, payload['new_index'], project)

    def is_new_index_created_if_yes_remove(self, response, payload, project):
        ''' Check if new_index gets created
            Check if new_index gets re-indexed and completed
            remove test new_index '''
        if project.indices is None or project.indices not in payload['indices']:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        else:
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_reindexer = Reindexer.objects.get(id=response.data['id'])
            print_output("Re-index task status: ", created_reindexer.task.status)
            self.assertEqual(created_reindexer.task.status, Task.STATUS_COMPLETED)
            new_index = response.data['new_index']
            delete_response = ElasticCore().delete_index(new_index)
            print_output("Reindexer Test index remove status", delete_response)

    def is_reindexed_index_added_to_project(self, response, new_index, project):
        check = self.client.get(f'/projects/{project.id}/', format='json')
        if response.status_code == 201:
            assert new_index in check.data['indices']
            print_output('Re-indexed index added to project', check.data)
        if response.status_code == 400:
            assert new_index not in check.data['indices']
            print_output('Re-indexed index not added to project', check.data)

    # no point in testing fields, before you implement changing them.



