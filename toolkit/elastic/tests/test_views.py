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
        cls.project_no_indices = Project.objects.create(
            title='ReindexerNoIndicesTestProject',
            owner=cls.user
            # either has no indices or those not contained in test_payload "indices"
        )

    def setUp(self):
        self.client.login(username='indexOwner', password='pw')

    def test_run(self):
        pick_fields_payload = {
            "description": "TestManyReindexerFields",
            # we can pick out fields present in TEST_INDEX
            "fields": [TEST_FIELD, 'comment_content_clean.text', 'content_entity_anonymous_sort_nr'],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [],
        }
        join_indices_fields_payload = {
            "description": "TestReindexerJoinFields",
            "fields": [],
            "indices": [TEST_INDEX, 'kuusalu_vv'],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [],
        }
        random_docs_payload = {
            "description": "TestReindexerRandomFields",
            "fields": [],
            "indices": [TEST_INDEX, 'kuusalu_vv'],
            "new_index": TEST_INDEX_REINDEX,
            "random_size": 500,
            "field_type": [],
        }
        update_field_type_payload = {
            "description": "TestReindexerUpdateFieldType",
            "fields": [],
            "indices": [TEST_INDEX, 'kuusalu_vv'],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [{"path": "comment_subject", "field_type": "long", "new_path_name": "CHANGED_NAME"},
                           {"path": "comment_content_lemmas", "field_type": "fact", "new_path_name": "CHANGED_TOO"},
                           {"path": "comment_content_clean.stats.text_length", "field_type": "boolean", "new_path_name": "CHANGED_AS_WELL"},
                           ],
            # "field_type": []
            # "field_type": [{"path": "comment_subject", "field_type": "long", "new_path_name": "changed_path_name"}],
            # "field_type": [{"path": "comment_subject", "new_path_name": "changed_path_name"}], #TODO

        }

        for project in (
                        self.project,
                        self.project_no_indices,    # indices validation failure test
                                                    # TODO: fields validation failure test
                        ):
            url =  f'/projects/{project.id}/reindexer/'
            self.run_create_reindexer_task_signal(project, url, pick_fields_payload) # kõik postitatud väjad uude indeksisse, kui valideeritud projekti kaudu

        for payload in (
                        join_indices_fields_payload,
                        random_docs_payload,
                        update_field_type_payload,
            ):
            url = f'/projects/{self.project.id}/reindexer/'
            self.run_create_reindexer_task_signal(self.project, url, payload)


    def run_create_reindexer_task_signal(self, project, url, payload, overwrite=False):
        ''' Tests the endpoint for a new Reindexer task, and if a new Task gets created via the signal
           checks if new_index was removed '''

        # ElasticCore().delete_index(TEST_INDEX_REINDEX)
        if overwrite == False and TEST_INDEX_REINDEX not in ElasticCore().get_indices():
            response = self.client.post(url, payload, format='json')
            print_output('run_create_reindexer_task_signal:response.data', response.data)
            self.is_reindexed_index_added_to_project_if_yes_remove(response, payload['new_index'], project)
            self.is_new_index_created_if_yes_remove(response, payload, project)
        assert TEST_INDEX_REINDEX not in ElasticCore().get_indices()

    def is_new_index_created_if_yes_remove(self, response, payload, project):
        ''' Check if new_index gets created
            Check if new_index gets re-indexed and completed
            remove test new_index '''
        if project.indices is None:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        else:
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_reindexer = Reindexer.objects.get(id=response.data['id'])
            print_output("Re-index task status: ", created_reindexer.task.status)
            self.assertEqual(created_reindexer.task.status, Task.STATUS_COMPLETED)
            new_index = response.data['new_index']
            delete_response = ElasticCore().delete_index(new_index)
            print_output("Reindexer Test index remove status", delete_response)

    def is_reindexed_index_added_to_project_if_yes_remove(self, response, new_index, project):
        url = f'/projects/{project.id}/'
        check = self.client.get(url, format='json')
        if response.status_code == 201:
            assert new_index in check.data['indices']
            print_output('Re-indexed index added to project', check.data)
            check.data['indices'] = [TEST_INDEX]
            self.client.put(url, check.data, format='json')

        if response.status_code == 400:
            assert new_index not in check.data['indices']
            print_output('Re-indexed index not added to project', check.data)









