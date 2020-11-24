import os
import pathlib

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Index
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH, SEARCHER_FOLDER_KEY
from toolkit.test_settings import REINDEXER_TEST_INDEX, TEST_FACT_NAME, TEST_INDEX, TEST_QUERY, TEST_VERSION_PREFIX
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

        self.admin = create_test_user(name='admin', password='pw')
        self.admin.is_superuser = True
        self.admin.save()

        self.project_user = create_test_user(name='project_user', password='pw')
        self.project = project_creation("testproj", TEST_INDEX, self.user)
        self.project.users.add(self.project_user)
        self.client = APIClient()
        self.client.login(username='project_user', password='pw')
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.export_url = reverse("v1:project-export-search", kwargs={"pk": self.project.pk})


    def __add_indices_to_project(self, index_names: []):
        for index in index_names:
            index_model, is_created = Index.objects.get_or_create(name=index)
            self.project.indices.add(index_model)


    def test_get_fields(self):
        url = f'{self.project_url}/get_fields/'
        response = self.client.get(url)
        print_output('get_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_INDEX in [field['index'] for field in response.data])


    def test_get_facts(self):
        url = f'{self.project_url}/get_facts/'
        response = self.client.post(url)
        print_output('get_facts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_FACT_NAME in [field['name'] for field in response.data])


    def test_get_facts_with_indices(self):
        url = f'{self.project_url}/get_facts/'
        response = self.client.post(url, format="json", data={"indices": [{"name": TEST_INDEX}]})
        print_output('get_facts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_FACT_NAME in [field['name'] for field in response.data])


    def test_search(self):
        payload = {"match_text": "jeesus", "size": 1}
        url = f'{self.project_url}/search/'
        response = self.client.post(url, payload)
        print_output('search:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(len(response.data) == 1)


    def test_search_match_phrase_empty_result(self):
        payload = {"match_text": "jeesus tuleb ja tapab kõik ära", "match_type": "phrase"}
        url = f'{self.project_url}/search/'
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
        payload = {"limit": 5, "startswith": "fo", "fact_name": TEST_FACT_NAME, "indices": [{"name": TEST_INDEX}]}
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
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(self.project.pk) / SEARCHER_FOLDER_KEY
        self.assertTrue(path.exists() is True)
        for path in path.glob("*.jl"):
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


    def test_search_by_query(self):
        url = f'{self.project_url}/search_by_query/'
        # check that project user has access and response is success
        self.client.login(username='project_usser', password='pw')
        payload = {"query": TEST_QUERY}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_project_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # test search with indices
        payload = {"query": TEST_QUERY, "indices": [TEST_INDEX]}
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_with_indices_project_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # check that non-project users do not have access
        self.client.login(username='user', password='pw')
        response = self.client.post(url, payload, format='json')
        print_output("search_by_query_no_access_user", response.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_project_creation_with_admin_user(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(reverse("v1:project-list"), format="json", data={
            "title": "faulty_project",
            "indices": [TEST_INDEX],
            "users": [reverse("v1:user-detail", args=[self.admin.pk])]
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_project_creation_with_normal_user(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(reverse("v1:project-list"), format="json", data={
            "title": "faulty_project",
            "indices": [TEST_INDEX],
            "users": [reverse("v1:user-detail", args=[self.user.pk])]
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        p = Project.objects.get(pk=response.data["id"])
        self.assertTrue(p.title == "faulty_project")
        self.assertTrue(p.indices.count() == 1)
        self.assertTrue(p.indices.get(name=TEST_INDEX) is not None)


    def test_project_updating_indices(self):
        self.client.login(username="admin", password="pw")
        ec = ElasticCore()
        ec.create_index("test_project_update")

        pk = Project.objects.last().pk
        url = reverse("v1:project-detail", args=[pk])
        payload = {
            "indices": [TEST_INDEX, "test_project_update"]
        }
        response = self.client.patch(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        project = Project.objects.get(pk=pk)
        self.assertTrue(project.indices.count() == 2)
        self.assertTrue(project.indices.get(name=TEST_INDEX) is not None)
        ec.delete_index("test_project_update")


    def test_project_creation_as_a_plebian_user(self):
        self.client.login(username="user", password="pw")
        response = self.client.post(reverse("v1:project-list"), format="json", data={
            "title": "faulty_project",
            "indices": [TEST_INDEX],
            "users": [reverse("v1:user-detail", args=[self.user.pk])]
        })
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_project_creation_with_unexisting_indices(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(reverse("v1:project-list"), format="json", data={
            "title": "faulty_project",
            "indices": ["the_holy_hand_granade"],
            "users": [reverse("v1:user-detail", args=[self.admin.pk])]
        })
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_project_update_with_unexisting_indices(self):
        self.client.login(username="admin", password="pw")
        pk = Project.objects.last().pk
        url = reverse("v1:project-detail", args=[pk])
        payload = {
            "indices": ["an_european_or_african_swallow"]
        }
        response = self.client.patch(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
