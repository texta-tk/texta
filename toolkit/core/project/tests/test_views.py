from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.tools.common_utils import project_creation
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit import permissions as toolkit_permissions
from toolkit.test_settings import TEST_INDEX, TEST_FACT_NAME, TEST_QUERY, TEST_VERSION_PREFIX


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
    def setUp(cls):
        # Create a new project_user, all project extra actions need to be permissible for this project_user.
        cls.user = create_test_user(name='user', password='pw')
        cls.project_user = create_test_user(name='project_user', password='pw')
        cls.project = project_creation("testproj", TEST_INDEX)
        cls.project.users.add(cls.project_user)
        cls.client = APIClient()
        cls.client.login(username='project_user', password='pw')
        cls.project_url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}'


    def test_get_fields(self):
        url = f'{self.project_url}/get_fields/'
        response = self.client.get(url)
        print_output('get_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_INDEX in [field['index'] for field in response.data])

    def test_get_facts(self):
        url = f'{self.project_url}/get_facts/'
        response = self.client.get(url)
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

    def test_autocomplete_fact_names(self):
        payload = {"limit": 5, "startswith": "TE" }
        url = f'{self.project_url}/autocomplete_fact_names/'
        print(url)
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
        self.assertTrue('num_embedding_clusters' in response.data)

    def test_get_indices(self):
        url = f'{self.project_url}/get_indices/'
        self.client.login(username='user', password='pw')

        response = self.client.get(url)
        print_output("get_indices", response.data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.login(username='project_user', password='pw')
        response = self.client.get(url)
        print_output("get_indices", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_by_query(self):
        url = f'{self.project_url}/search_by_query/'
        # check that project user has access and response is success
        self.client.login(username='project_user', password='pw')
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

