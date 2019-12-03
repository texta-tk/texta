import os
import json
from time import sleep

from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_INDEX_REINDEX, TEST_INDEX_LARGE, TEST_QUERY, REINDEXER_TEST_INDEX
from toolkit.core.project.models import Project
from toolkit.elastic.models import Reindexer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class ReindexerViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        ''' user needs to be admin, because of changed indices permissions '''
        cls.default_password = 'pw'
        cls.default_username = 'indexOwner'
        cls.user = create_test_user(cls.default_username, 'my@email.com', cls.default_password)
        cls.user.is_superuser = True
        cls.user.save()
        cls.project = Project.objects.create(
            title='ReindexerTestProject',
            owner=cls.user,
            indices=[TEST_INDEX]
        )

    def setUp(self):
        self.client.login(username=self.default_username, password=self.default_password)

    def test_run(self):
        existing_new_index_payload = {
        "description": "TestWrongField",
        "indices": [TEST_INDEX],
        "new_index": REINDEXER_TEST_INDEX,  # index created for test purposes
        "fields": [],
        "field_type": [],
        }
        wrong_fields_payload = {
        "description": "TestWrongField",
        "indices": [TEST_INDEX],
        "new_index": TEST_INDEX_REINDEX,
        "fields": ['12345'],
        }
        wrong_indices_payload = {
        "description": "TestWrongIndex",
        "indices": ["Wrong_Index"],
        "new_index": TEST_INDEX_REINDEX,
        "fields": [],
        }
        pick_fields_payload = {
            "description": "TestManyReindexerFields",
            # this has a problem with possible name duplicates
            "fields": [TEST_FIELD, 'comment_content_clean.text', 'texta_facts'],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [],
        }
        # duplicate name problem?
        # if you want to actually test it, add an index to indices and project indices
        join_indices_fields_payload = {
            "description": "TestReindexerJoinFields",
            "fields": [],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [],
        }
        test_query_payload = {
            "description": "TestQueryFiltering",
            "fields": [],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [],
            "query": json.dumps(TEST_QUERY)
        }
        random_docs_payload = {
            "description": "TestReindexerRandomFields",
            "fields": [],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "random_size": 500,
            "field_type": [],
        }
        update_field_type_payload = {
            "description": "TestReindexerUpdateFieldType",
            "fields": [],
            "indices": [TEST_INDEX],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [{"path": "comment_subject", "field_type": "long", "new_path_name": "CHANGED_NAME"},
                           {"path": "comment_content_lemmas", "field_type": "fact", "new_path_name": "CHANGED_TOO"},
                           {"path": "comment_content_clean.stats.text_length", "field_type": "boolean", "new_path_name": "CHANGED_AS_WELL"},
                           ],
        }
        for payload in (
            existing_new_index_payload,
            wrong_indices_payload,
            wrong_fields_payload,
            pick_fields_payload,
            join_indices_fields_payload,
            test_query_payload,
            random_docs_payload,
            update_field_type_payload,
        ):
            url = f'/projects/{self.project.id}/reindexer/'
            self.run_create_reindexer_task_signal(self.project, url, payload)

    def run_create_reindexer_task_signal(self, project, url, payload, overwrite=False):
        ''' Tests the endpoint for a new Reindexer task, and if a new Task gets created via the signal
           checks if new_index was removed '''
        try:
            ElasticCore().delete_index(TEST_INDEX_REINDEX)
        except:
               print(f'{TEST_INDEX_REINDEX} was not deleted')
        response = self.client.post(url, payload, format='json')
        print_output('run_create_reindexer_task_signal:response.data', response.data)
        self.check_update_forbidden(url, payload)
        self.is_new_index_created_if_yes_remove(response, payload, project)
        self.is_reindexed_index_added_to_project_if_yes_remove(response, payload['new_index'], project)
        assert TEST_INDEX_REINDEX not in ElasticCore().get_indices()

    def is_new_index_created_if_yes_remove(self, response, payload, project):
        ''' Check if new_index gets created
            Check if new_index gets re-indexed and completed
            remove test new_index '''

        if project.indices is None or response.exception:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        else:
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_reindexer = Reindexer.objects.get(id=response.data['id'])
            print_output("Re-index task status: ", created_reindexer.task.status)
            self.assertEqual(created_reindexer.task.status, Task.STATUS_COMPLETED)
            self.check_positive_doc_count()
            new_index = response.data['new_index']
            delete_response = ElasticCore().delete_index(new_index)
            print_output("Reindexer Test index remove status", delete_response)

    def is_reindexed_index_added_to_project_if_yes_remove(self, response, new_index, project):
        url = f'/projects/{project.id}/'
        check = self.client.get(url, format='json')
        if response.status_code == 201:
            assert new_index in check.data['indices']
            print_output('Re-indexed index added to project', check.data)
            check.data['indices'].remove(new_index)
            remove_response = self.client.put(url, check.data, format='json')
            print_output("Re-indexed index removed from project", remove_response.status_code)
        if response.status_code == 400:
            print_output('Re-indexed index not added to project', check.data)
        assert new_index not in check.data['indices']

    def validate_fields(self, project, payload):
        project_fields = ElasticCore().get_fields(project.indices)
        project_field_paths = [field["path"] for field in project_fields]
        for field in payload['fields']:
            if field not in project_field_paths:
                return False
        return True

    def validate_indices(self, project, payload):
        for index in payload['indices']:
            if index not in project.indices:
                return False
        return True

    def check_positive_doc_count(self):
        # current reindexing tests require approx 2 seconds delay
        sleep(1.8)
        count_new_documents = ElasticSearcher(indices=TEST_INDEX_REINDEX).count()
        print_output("Bulk add doc count", count_new_documents)
        assert count_new_documents > 0

    def check_update_forbidden(self, url, payload):
        put_response = self.client.put(url, payload, format='json')
        patch_response = self.client.patch(url, payload, format='json')
        print_output("put_response.data", put_response.data)
        print_output("patch_response.data", patch_response.data)
        self.assertEqual(put_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(patch_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)




