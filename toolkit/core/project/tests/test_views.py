import os
import pathlib
import uuid
import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from texta_elastic.core import ElasticCore
from time import sleep

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH, SEARCHER_FOLDER_KEY
from toolkit.test_settings import REINDEXER_TEST_INDEX, TEST_INDEX, TEST_FACT_NAME, TEST_FIELD, TEST_MATCH_TEXT, TEST_QUERY, TEST_VERSION_PREFIX, VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class ProjectViewTests(APITestCase):
    """ since permissions are project based, project PUT/PATCH is tested in the permissions package
     all project extra actions must be accessible for project users:
        get_fields,
        get_facts,
        search,
        autocomplete_fact_values,
        autocomplete_fact_names,
        get_resource_counts,
        tested in tagger -> multitag_text,
        get_indices,
        in separate file -> get_spam
    """


    def setUp(self):
        # Create a new project_user, all project extra actions need to be permissible for this project_user.
        self.user = create_test_user(name='user', password='pw')
        self.project_user = create_test_user(name='project_user', password='pw')
        self.admin = create_test_user(name='admin', password='pw')
        self.admin.is_superuser = True
        self.admin.save()
        self.project_name = "testproj"
        self.project = project_creation(self.project_name, TEST_INDEX, self.user)
        self.project.users.add(self.project_user)
        self.project.save()
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.export_url = reverse(f"{VERSION_NAMESPACE}:project-export-search", kwargs={"project_pk": self.project.pk})

        self.client = APIClient()
        self.client.login(username='project_user', password='pw')


    def __reindex_test_index(self):
        self.test_index_name = reindex_test_dataset()
        self.__add_indices_to_project([self.test_index_name])


    def __remove_reindexed_test_index(self):
        ec = ElasticCore()
        result = ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Deleting ProjectViewTests test index {self.test_index_name}", result)


    def __create_project(self):
        payload = {"title": "this is a nightmare!"}
        url = reverse("v2:project-list")
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        return Project.objects.get(pk=response.data["id"])


    def __add_indices_to_project(self, index_names: []):
        for index in index_names:
            index_model, is_created = Index.objects.get_or_create(name=index)
            self.project.indices.add(index_model)
        self.project.save()


    def test_get_fields(self):
        url = f'{self.project_url}/elastic/get_fields/'
        response = self.client.get(url)
        print_output('get_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_INDEX in [field['index'] for field in response.data])


    def test_get_facts(self):
        url = f'{self.project_url}/elastic/get_facts/'
        response = self.client.post(url)
        print_output('get_facts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_FACT_NAME in [field['name'] for field in response.data])


    def test_get_facts_with_exclude_zero_spans(self):
        """Tests get_facts endpoint with param 'exclude_zero_spans'."""
        self.__reindex_test_index()
        # Add facts for testing
        doc_id = str(uuid.uuid4())
        ec = ElasticCore()
        test_facts = [
            {"str_val": "dracula", "fact": "MONSTER", "spans": json.dumps([[17,28]]), "doc_path": "text_mlp.text"},
            {"str_val": "potato", "fact": "FOOD", "spans": json.dumps([[0,0]]), "doc_path": "text"},
            {"str_val": "titanic", "fact": "BOAT", "spans": json.dumps([[18,38]]), "doc_path": "text_mlp.text_mlp.lemmas"},
            {"str_val": "cat", "fact": "ANIMAL", "spans": json.dumps([[0,0]]), "doc_path": "text"}
        ]
        es_response = ec.es.index(index=self.test_index_name, id=doc_id, body={"texta_facts": test_facts}, refresh="wait_for")
        print_output('test_get_facts_with_exclude_zero_spans:es.index.response', es_response)
        url = f'{self.project_url}/elastic/get_facts/'
        response = self.client.post(url, data={"exclude_zero_spans": True, "include_values": False}, format="json")
        print_output('test_get_facts_with_exclude_zero_spans:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue("MONSTER" in response.data)
        self.assertTrue("BOAT" in response.data)
        self.assertFalse("FOOD" in response.data)
        self.assertFalse("ANIMAL" in response.data)
        self.__remove_reindexed_test_index()


    def test_get_facts_with_mlp_doc_path_and_spans(self):
        """Tests get_facts endpoint with param 'exclude_zero_spans' and 'mlp_doc_path'."""
        self.__reindex_test_index()
        # Add facts for testing
        doc_id = str(uuid.uuid4())
        ec = ElasticCore()
        test_facts = [
            {"str_val": "dracula", "fact": "MONSTER", "spans": json.dumps([[17,28]]), "doc_path": "text_mlp.text"},
            {"str_val": "potato", "fact": "FOOD", "spans": json.dumps([[18,38]]), "doc_path": "text"},
            {"str_val": "titanic", "fact": "BOAT", "spans": json.dumps([[18,38]]), "doc_path": "text_mlp.text_mlp.lemmas"},
            {"str_val": "cat", "fact": "ANIMAL", "spans": json.dumps([[0,0]]), "doc_path": "text"}
        ]
        es_response = ec.es.index(index=self.test_index_name, id=doc_id, body={"texta_facts": test_facts}, refresh="wait_for")
        print_output('test_get_facts_with_mlp_doc_path_and_spans:es.index.response', es_response)
        url = f'{self.project_url}/elastic/get_facts/'
        response = self.client.post(url, data={"indices": [{"name": self.test_index_name}], "exclude_zero_spans": True, "mlp_doc_path": "text_mlp"}, format="json")
        print_output('test_get_facts_with_mlp_doc_path_and_spans:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue("MONSTER" in response.data)
        self.assertFalse("BOAT" in response.data)
        self.assertFalse("FOOD" in response.data)
        self.assertFalse("ANIMAL" in response.data)
        self.__remove_reindexed_test_index()


    def test_get_facts_with_indices(self):
        url = f'{self.project_url}/elastic/get_facts/'
        response = self.client.post(url, format="json", data={"indices": [{"name": TEST_INDEX}]})
        print_output('get_facts_with_indices:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_FACT_NAME in [field['name'] for field in response.data])


    def test_get_facts_with_include_doc_path(self):
        url = f'{self.project_url}/elastic/get_facts/'
        response = self.client.post(url, format="json", data={"include_doc_path": True})
        print_output('get_facts_with_include_doc_path:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        for field in response.data:
            for value in field['values']:
                self.assertTrue('doc_path' in value)


    def test_aggregate_facts(self):
        url = f'{self.project_url}/elastic/aggregate_facts/'

        payload = {
            "incides": [{"name": TEST_INDEX}],
            "key_field": "fact",
            "value_field": "doc_path"
        }
        response = self.client.post(url, payload)
        print_output('project:aggregate_facts:key=fact:value=doc_path:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue(TEST_FACT_NAME in response.data)
        self.assertTrue("comment_content" in response.data[TEST_FACT_NAME])

        payload = {
            "incides": [{"name": TEST_INDEX}],
            "key_field": "doc_path",
            "value_field": "fact",
            "filter_by_key": "comment_content"
        }

        response = self.client.post(url, payload)
        print_output('project:aggregate_facts:key=doc_path:value=fact:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_FACT_NAME in response.data)


    def test_aggregate_facts_invalid(self):
        url = f'{self.project_url}/elastic/aggregate_facts/'

        payload = {
            "incides": [{"name": TEST_INDEX}],
            "key_field": "fact",
            "value_field": "fact"
        }
        response = self.client.post(url, payload)
        print_output('project:aggregate_facts_invalid_input:key=fact:value=fact:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payload = {
            "incides": [{"name": TEST_INDEX}],
            "key_field": "fact",
            "value_field": "brr"
        }
        response = self.client.post(url, payload)
        print_output('project:aggregate_facts_invalid_input:key=fact:value=brr:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_search(self):
        payload = {"match_text": "jeesus", "size": 1}
        url = f'{self.project_url}/elastic/search/'
        response = self.client.post(url, payload)
        print_output('search:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(len(response.data) == 1)


    def test_search_match_phrase_empty_result(self):
        payload = {"match_text": "jeesus tuleb ja tapab kõik ära", "match_type": "phrase"}
        url = f'{self.project_url}/elastic/search/'
        response = self.client.post(url, payload)
        print_output('search:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(len(response.data) == 0)


    def test_autocomplete_fact_values(self):
        payload = {"limit": 5, "startswith": "fo", "fact_name": TEST_FACT_NAME}
        url = f'{self.project_url}/autocomplete_fact_values/'
        response = self.client.post(url, payload)
        print_output('test_autocomplete_fact_values:response.data', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('foo' in response.data)
        self.assertTrue('bar' not in response.data)


    def test_autocomplete_fact_values_with_indices(self):
        payload = {"limit": 5, "startswith": "fo", "fact_name": TEST_FACT_NAME, "indices": [TEST_INDEX]}
        url = f'{self.project_url}/autocomplete_fact_values/'
        response = self.client.post(url, payload)
        print_output('test_autocomplete_fact_values:response.data', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('foo' in response.data)
        self.assertTrue('bar' not in response.data)


    def test_autocomplete_fact_values_with_empty_indices(self):
        payload = {"limit": 5, "startswith": "fo", "fact_name": TEST_FACT_NAME, "indices": []}
        url = f'{self.project_url}/autocomplete_fact_values/'
        response = self.client.post(url, payload)
        print_output('test_autocomplete_fact_values:response.data', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('foo' in response.data)
        self.assertTrue('bar' not in response.data)


    def test_autocomplete_fact_names(self):
        payload = {"limit": 5, "startswith": "TE"}
        url = f'{self.project_url}/autocomplete_fact_names/'
        response = self.client.post(url, payload)
        print_output('test_autocomplete_fact_names:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('TEEMA' in response.data)


    def test_autocomplete_fact_names_with_indices(self):
        payload = {"limit": 5, "startswith": "TE", "indices": [{"name": TEST_INDEX}]}
        url = f'{self.project_url}/autocomplete_fact_names/'
        response = self.client.post(url, payload)
        print_output('test_autocomplete_fact_names:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('TEEMA' in response.data)


    def test_resource_counts(self):
        url = f'{self.project_url}/get_resource_counts/'
        response = self.client.get(url)
        print_output('get_resource_counts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('num_torchtaggers' in response.data)
        self.assertTrue('num_taggers' in response.data)
        self.assertTrue('num_tagger_groups' in response.data)
        self.assertTrue('num_embeddings' in response.data)
        self.assertTrue('num_clusterings' in response.data)
        self.assertTrue('num_regex_taggers' in response.data)
        self.assertTrue('num_regex_tagger_groups' in response.data)
        self.assertTrue('num_anonymizers' in response.data)
        self.assertTrue('num_mlp_workers' in response.data)
        self.assertTrue('num_reindexers' in response.data)
        self.assertTrue('num_dataset_importers' in response.data)


    def test_search_export(self):
        payload = {"indices": [TEST_INDEX, REINDEXER_TEST_INDEX]}
        response = self.client.post(self.export_url, data=payload, format="json")
        hosted_url = response.data
        file_name = hosted_url.split("/")[-1]
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(self.project.pk) / SEARCHER_FOLDER_KEY / file_name
        self.assertTrue(path.exists() is True)

        file_size = os.path.getsize(path)
        self.assertTrue(file_size > 1)  # Check that file actually has content

        # Check if file is downloadable.
        response = self.client.get(hosted_url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        # Try to access it without authorization.
        self.client.logout()
        response = self.client.get(hosted_url)
        self.assertTrue(response.status_code != status.HTTP_200_OK)


    def test_search_export_with_invalid_query(self):
        payload = {"indices": [TEST_INDEX], "query": {"this": "is invalid"}}
        response = self.client.post(self.export_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_search_export_with_all_fields(self):
        payload = {"indices": [TEST_INDEX], "fields": []}
        response = self.client.post(self.export_url, data=payload, format="json")
        print_output("test_search_export_with_all_fields:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        hosted_url = response.data
        file_name = hosted_url.split("/")[-1]
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(self.project.pk) / SEARCHER_FOLDER_KEY / file_name
        file_size = os.path.getsize(path)
        self.assertTrue(file_size > 1)


    def test_search_by_query(self):
        url = f'{self.project_url}/elastic/search_by_query/'
        # check that project user has access and response is success
        self.client.login(username='project_user', password='pw')
        payload = {"query": TEST_QUERY}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_project_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # test search with indices
        highlight_query = {"query": {"match": {TEST_FIELD: {"query": TEST_MATCH_TEXT}}},
                           "highlight": {"fields": {TEST_FIELD: {}}, "number_of_fragments": 0, }}
        payload = {"query": highlight_query, "indices": [TEST_INDEX]}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_with_indices_project_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data['results'][0]['highlight'], dict))
        # test search with output type raw
        payload = {"query": highlight_query, "indices": [TEST_INDEX], "output_type": 'raw'}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_with_output_type_raw", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data['hits']['hits'][0]['_source']['comment_content_clean'], dict))
        # test search with output type doc_with_id
        payload = {"query": highlight_query, "indices": [TEST_INDEX], "output_type": 'doc_with_id'}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_with_output_type_doc_with_id", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data['hits']['hits'][0]['_source']['comment_content_clean.text'], str))
        # check that non-project users do not have access
        self.client.login(username='user', password='pw')
        self.project.users.remove(self.user)
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_no_access_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_project_creation_with_admin_user(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(reverse(f"{VERSION_NAMESPACE}:project-list"), format="json", data={
            "title": "faulty_project",
            "indices_write": [TEST_INDEX],
            "users_write": [self.admin.username]
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_project_creation_with_normal_user(self):
        self.client.login(username="admin", password="pw")
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        response = self.client.post(url, format="json", data={
            "title": "faulty_project",
            "indices_write": [TEST_INDEX],
            "users_write": [self.user.username]
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        p = Project.objects.get(pk=response.data["id"])
        self.assertTrue(p.title == "faulty_project")
        self.assertTrue(p.indices.count() == 1)
        self.assertTrue(p.indices.get(name=TEST_INDEX) is not None)


    def test_project_creation_with_unexisting_indices(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(reverse(f"{VERSION_NAMESPACE}:project-list"), format="json", data={
            "title": "faulty_project",
            "indices_write": ["unexisting_index_that_throws_error"],
            "users_write": [self.admin.username]
        })
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_project_update_with_unexisting_indices(self):
        self.client.login(username="admin", password="pw")
        pk = Project.objects.last().pk
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", args=[pk])
        payload = {
            "indices_write": ["unexisting_index_that_throws_an_error"]
        }
        response = self.client.patch(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_document_count(self):
        url = reverse("v2:project-count-indices", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"indices": [TEST_INDEX]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, int))
        self.assertTrue(response.data > 100)


    def test_document_count_with_false_indies(self):
        url = reverse("v2:project-count-indices", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"indices": [TEST_INDEX + "_potato"]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_document_count_with_zero_input(self):
        url = reverse("v2:project-count-indices", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"indices": []}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data == 0)


    def test_that_superadmins_can_see_all_projects(self):
        self.client.login(username="admin", password="pw")
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        response = self.client.get(url)
        print_output("test_that_superadmins_can_see_all_projects:response.data", response.data)
        self.assertTrue(len(response.data) == 1)


    def test_that_normal_users_can_see_only_projects_they_author_or_admin(self):
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        project_for_project_user = self.__create_project()
        self.client.login(username="user", password="pw")

        response = self.client.get(url)
        self.assertTrue(len(response.data) == 1)

        self.client.login(username="project_user", password="pw")
        response = self.client.get(url)
        print_output("test_that_normal_users_can_see_only_projects_they_author_or_admin:response.data", response.data)
        self.assertTrue(len(response.data) == 2)


    def test_that_normal_user_cant_add_indices(self):
        url = reverse(f"{VERSION_NAMESPACE}:project-add-indices", kwargs={"pk": self.project.pk})
        index = Index.objects.get(name=TEST_INDEX)
        response = self.client.post(url, data={"indices": [index.pk]}, format="json")
        print_output("test_that_normal_user_cant_add_indices:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_that_normal_user_can_not_create_project_with_indices(self):
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        payload = {"title": "the holy hand grenade", "indices_write": [TEST_INDEX]}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_that_normal_user_can_not_create_project_with_indices:response.data", response.data)
        self.assertTrue(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_project_creation_with_normal_user_and_only_title(self):
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        payload = {"title": "the holy hand grenade"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_project_creation_with_normal_user_and_only_title:response.data", response.data)
        self.assertTrue(response.status_code, status.HTTP_201_CREATED)


    def test_nonsuperadmin_and_nonadmin_trying_to_edit_wrong_project(self):
        self.client.login(username="user", password="pw")
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", kwargs={"pk": self.project.pk})
        response = self.client.patch(url, data={"title": "the holy hand grenade!"}, format="json")
        print_output("test_nonsuperadmin_and_nonadmin_trying_to_edit_wrong_project", response.data)
        self.assertTrue(response.status_code, status.HTTP_404_NOT_FOUND)


    def test_that_project_admin_can_edit_title(self):
        project = self.__create_project()
        self.assertTrue(self.project_user in project.administrators.all())
        new_title = "holy hand grenade"
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", kwargs={"pk": project.pk})
        response = self.client.patch(url, data={"title": new_title}, format="json")
        print_output("test_that_project_admin_can_edit_title:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        project = Project.objects.get(pk=project.pk)
        self.assertTrue(project.title != self.project_name and project.title == new_title)


    def test_that_project_administrator_can_edit_users(self):
        project = self.__create_project()
        self.assertTrue(self.project_user in project.administrators.all())
        url = reverse(f"{VERSION_NAMESPACE}:project-add-users", kwargs={"pk": project.pk})
        response = self.client.post(url, data={"users": [self.user.pk]}, format="json")
        print_output("test_that_project_administrator_can_edit_users:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_that_superadmin_can_delete_project(self):
        self.client.login(username="admin", password="pw")
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", kwargs={"pk": self.project.pk})
        response = self.client.delete(url)
        print_output("test_that_superadmin_can_delete_project:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_204_NO_CONTENT)


    def test_that_project_admin_can_delete_project(self):
        # Create a test project.
        payload = {"title": "test_project"}
        url = reverse(f"{VERSION_NAMESPACE}:project-list")
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        # Ensure that the user who created it is an project admin.
        project = Project.objects.get(pk=response.data["id"])
        self.assertTrue(self.project_user in project.administrators.all())

        # Check for deletion.
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", kwargs={"pk": project.pk})
        response = self.client.delete(url)
        print_output("test_that_project_admin_can_delete_project:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_204_NO_CONTENT)


    def test_that_normal_user_cant_delete_project(self):
        self.client.login(username="user", password="pw")
        url = reverse(f"{VERSION_NAMESPACE}:project-detail", kwargs={"pk": self.project.pk})
        response = self.client.delete(url)
        print_output("test_that_normal_user_cant_delete_project:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_that_normal_users_cant_add_project_admins(self):
        self.client.login(username="user", password="pk")
        url = reverse(f"{VERSION_NAMESPACE}:project-add-project-admins", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"proj_admins": [self.project_user.pk]})
        print_output("test_that_normal_users_cant_add_project_admins:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_that_project_authors_and_projadmins_can_add_projadmins(self):
        project = self.__create_project()
        self.assertTrue(self.project_user in project.administrators.all())
        url = reverse(f"{VERSION_NAMESPACE}:project-add-project-admins", kwargs={"pk": project.pk})
        response = self.client.post(url, data={"project_admins": [self.user.pk]})
        print_output("test_that_project_authors_and_projadmins_can_add_projadmins:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    # def test_project_creation_with_scope(self):
    #     pass
    #
    #
    # def test_updating_scopes(self):
    #     pass
    #
    #
    # def test_that_normal_users_can_only_add_scopes_they_are_in(self):
    #     pass
    #
    #
    # def test_that_admins_can_pick_any_scope_they_want_to(self):
    #     pass
