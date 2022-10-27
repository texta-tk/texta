import json
import uuid
from time import sleep

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher

from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import TEXTA_TAGS_KEY
from toolkit.test_settings import *
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class ReindexerViewTests(APITransactionTestCase):

    def setUp(self):
        """ user needs to be admin, because of changed indices permissions """
        self.test_index_name = reindex_test_dataset()
        self.default_password = 'pw'
        self.default_username = 'indexOwner'
        self.user = create_test_user(self.default_username, 'my@email.com', self.default_password)

        # create admin to test indices removal from project
        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        self.admin.save()
        self.project = project_creation("ReindexerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)

        self.mlp_test_index = self._setup_mlp_test_requirements()
        self.mlp_index = Index.objects.create(name=self.mlp_test_index)
        self.project.indices.add(self.mlp_index)

        self.ec = ElasticCore()
        self.client.login(username=self.default_username, password=self.default_password)

        self.new_index_name = f"{TEST_FIELD}_2"


    def tearDown(self) -> None:
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        self.ec.delete_index(index=self.mlp_test_index, ignore=[400, 404])


    def _setup_mlp_test_requirements(self) -> str:
        document = {
            "comment_subject": "to lohutu",
            "comment_content": "Mis ajast homode vastasus määrab IQ-d.\nSelline arutlus sinult viitab sinu rumalusele,kel pole aimugu IQ-st",
            "_mlp_meta": {
                "comment_content": {
                    "spans": "text",
                    "analyzers": ["lemmas", "ner", "pos_tags"],
                    "tokenization": "text"
                },
                "comment_subject": {
                    "spans": "text",
                    "analyzers": ["lemmas", "pos_tags", "ner"],
                    "tokenization": "text"
                }
            }
        }
        ec = ElasticCore()
        test_index = f"texta_test_reindexer_mlp_{uuid.uuid4().hex}"
        ec.create_index(test_index)
        ec.es.index(index=test_index, body=document, refresh="wait_for")
        return test_index


    def test_reindexing_documents_with_mlp_keeps_meta_information(self):
        field_name = "comment_content"
        new_index = f"{self.mlp_test_index}_2"
        payload = {
            "description": "Test that MLP meta is kept for specific fields.",
            "fields": [field_name],
            "indices": [self.mlp_test_index],
            "new_index": new_index,
            "field_type": [{"path": field_name, "field_type": "text", "new_path_name": field_name}]
        }
        url = reverse(f"{VERSION_NAMESPACE}:reindexer-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_reindexing_documents_with_mlp_keeps_meta_information:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        result = self.ec.es.search(index=new_index)
        hits = result["hits"]["hits"]
        self.assertTrue(len(hits) == 1)  # Ensure that the index only has a single hit and setup was proper.
        mlp_meta = hits[0]["_source"]["_mlp_meta"]
        self.assertTrue(field_name in mlp_meta)  # Ensure that the field we reindexed was automatically included.
        self.assertTrue(len(mlp_meta.keys()) == 1)  # Ensure that ONLY the fields we wanted are included.


    def test_run(self):
        existing_new_index_payload = {
            "description": "TestWrongField",
            "indices": [self.test_index_name],
            "new_index": REINDEXER_TEST_INDEX,  # index created for test purposes
        }
        wrong_fields_payload = {
            "description": "TestWrongField",
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
            "fields": ['12345'],
        }
        wrong_indices_payload = {
            "description": "TestWrongIndex",
            "indices": ["Wrong_Index"],
            "new_index": TEST_INDEX_REINDEX,
        }
        pick_fields_payload = {
            "description": "TestManyReindexerFields",
            # this has a problem with possible name duplicates
            "fields": [TEST_FIELD, 'comment_content_clean.text', 'texta_facts'],
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
        }
        # duplicate name problem?
        # if you want to actually test it, add an index to indices and project indices
        join_indices_fields_payload = {
            "description": "TestReindexerJoinFields",
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
        }
        test_query_payload = {
            "description": "TestQueryFiltering",
            "scroll_size": 100,
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
            "query": json.dumps(TEST_QUERY)
        }
        random_docs_payload = {
            "description": "TestReindexerRandomFields",
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
            "random_size": 500,
        }

        update_field_type_payload = {
            "description": "TestReindexerUpdateFieldType",
            "fields": [],
            "indices": [self.test_index_name],
            "new_index": TEST_INDEX_REINDEX,
            "field_type": [{"path": "comment_subject", "field_type": "long", "new_path_name": "CHANGED_NAME"},
                           {"path": "comment_content_lemmas", "field_type": "fact", "new_path_name": "CHANGED_TOO"},
                           {"path": "comment_content_clean.stats.text_length", "field_type": "boolean",
                            "new_path_name": "CHANGED_AS_WELL"},
                           ],
        }
        for REINDEXER_VALIDATION_TEST_INDEX in (
                REINDEXER_VALIDATION_TEST_INDEX_1,
                REINDEXER_VALIDATION_TEST_INDEX_2,
                REINDEXER_VALIDATION_TEST_INDEX_3,
                REINDEXER_VALIDATION_TEST_INDEX_4,
                REINDEXER_VALIDATION_TEST_INDEX_5,
                REINDEXER_VALIDATION_TEST_INDEX_6
        ):
            new_index_validation_payload = {
                "description": "TestNewIndexValidation",
                "indices": [self.test_index_name],
                "new_index": REINDEXER_VALIDATION_TEST_INDEX
            }
            url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
            self.check_new_index_validation(url, new_index_validation_payload)

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
            url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
            self.run_create_reindexer_task_signal(self.project, url, payload)

        # Test that usernames are automatically added.
        self.assertTrue(Index.objects.filter(name=TEST_INDEX_REINDEX, added_by=self.default_username).exists())


    def run_create_reindexer_task_signal(self, project, url, payload, overwrite=False):
        """ Tests the endpoint for a new Reindexer task, and if a new Task gets created via the signal
           checks if new_index was removed """
        try:
            self.ec.delete_index(TEST_INDEX_REINDEX)
        except:
            print_output(f'{TEST_INDEX_REINDEX} was not deleted', payload)
        response = self.client.post(url, payload, format='json')
        print_output('run_create_reindexer_task_signal:response.data', response.data)
        self.check_update_forbidden(url, payload)
        self.is_new_index_created_if_yes_remove(response, payload, project)
        self.is_reindexed_index_added_to_project_if_yes_remove(response, payload['new_index'], project)
        assert TEST_INDEX_REINDEX not in ElasticCore().get_indices()


    def check_new_index_validation(self, url, new_index_validation_payload):
        response = self.client.post(url, new_index_validation_payload, format='json')
        print_output('new_index_validation:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"].code, "invalid_index_name")


    def is_new_index_created_if_yes_remove(self, response, payload, project):
        """ Check if new_index gets created
            Check if new_index gets re-indexed and completed
            remove test new_index """
        if project.get_indices() is None or response.exception:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        else:
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_reindexer = Reindexer.objects.get(id=response.data['id'])
            task_object = created_reindexer.tasks.last()
            print_output("Re-index task status: ", task_object.status)
            self.assertEqual(task_object.status, Task.STATUS_COMPLETED)
            # self.check_positive_doc_count()
            new_index = response.data['new_index']
            delete_response = self.ec.delete_index(new_index)
            print_output("Reindexer Test index remove status", delete_response)


    def is_reindexed_index_added_to_project_if_yes_remove(self, response, new_index, project):
        # project resource user is not supposed to have indices remove permission, so use admin
        self.client.login(username='admin', password='1234')
        url = f'{TEST_VERSION_PREFIX}/projects/{project.id}/'
        check = self.client.get(url, format='json')
        if response.status_code == 201:
            assert new_index in [index["name"] for index in check.data['indices']]
            print_output('Re-indexed index added to project', check.data)
            index_pk = Index.objects.get(name=new_index).pk
            remove_index_url = reverse(f"{VERSION_NAMESPACE}:project-remove-indices", kwargs={"pk": self.project.pk})
            remove_response = self.client.post(remove_index_url, {"indices": [index_pk]}, format='json')
            print_output("Re-indexed index removed from project", remove_response.status_code)
            self.delete_reindexing_task(project, response)

        if response.status_code == 400:
            print_output('Re-indexed index not added to project', check.data)

        check = self.client.get(url, format='json')
        assert new_index not in [index["name"] for index in check.data['indices']]
        # Log in with project user again
        self.client.login(username=self.default_username, password=self.default_password)


    def validate_fields(self, project, payload):
        project_fields = self.ec.get_fields(project.get_indices())
        project_field_paths = [field["path"] for field in project_fields]
        for field in payload['fields']:
            if field not in project_field_paths:
                return False
        return True


    def validate_indices(self, project, payload):
        for index in payload['indices']:
            if index not in project.get_indices():
                return False
        return True


    def check_positive_doc_count(self):
        # current reindexing tests require approx 2 seconds delay
        sleep(5)
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


    def delete_reindexing_task(self, project, response):
        """ test delete reindex task """
        task_url = response.data['url']
        get_response = self.client.get(task_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        delete_response = self.client.delete(task_url, format='json')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        get_response = self.client.get(task_url)
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)


    def test_that_changing_field_names_works(self):
        payload = {
            "description": "RenameFieldName",
            "new_index": self.new_index_name,
            "fields": [TEST_FIELD],
            "field_type": [{"path": TEST_FIELD, "new_path_name": TEST_FIELD_RENAMED, "field_type": "text"}],
            "indices": [self.test_index_name],
            "add_facts_mapping": True
        }

        # Reindex the test index into a new one.
        url = reverse("v2:reindexer-list", kwargs={"project_pk": self.project.pk})
        reindex_response = self.client.post(url, data=payload, format='json')
        print_output('test_that_changing_field_names_works:response.data', reindex_response.data)

        # Check that the fields have been changed.
        es = ElasticSearcher(indices=[self.new_index_name])
        for document in es:
            self.assertTrue(TEST_FIELD not in document)
            self.assertTrue(TEST_FIELD_RENAMED in document)

        # Manual clean up.
        es.core.delete_index(self.new_index_name)


    def test_that_texta_facts_structure_is_nested(self):
        payload = {
            "description": "TestTextaFacts",
            "new_index": self.new_index_name,
            "fields": [TEST_FIELD, TEXTA_TAGS_KEY],
            "indices": [self.test_index_name],
            "add_facts_mapping": True
        }

        # Reindex the test index into a new one.
        url = reverse("v2:reindexer-list", kwargs={"project_pk": self.project.pk})
        reindex_response = self.client.post(url, data=payload, format='json')
        print_output('test_that_texta_facts_structure_is_nested:response.data', reindex_response.data)

        # Check that the fields have been changed.

        mapping = self.ec.get_mapping(self.new_index_name)
        print_output("reindexed_mapping.data", mapping)
        facts_mapping = mapping[self.new_index_name]["mappings"]["properties"]["texta_facts"]
        self.assertTrue(facts_mapping["type"] == "nested")

        # Manual clean up.
        self.ec.delete_index(self.new_index_name)
