from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from texta_elastic.searcher import EMPTY_QUERY
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class ScrollApiTests(APITestCase):

    def setUp(self):
        # Create a new project_user, all project extra actions need to be permissible for this project_user.
        self.user = create_test_user(name='user', password='pw')
        self.unowned_user = create_test_user(name='unowned_user', password='pw')

        self.admin = create_test_user(name='admin', password='pw')
        self.admin.is_superuser = True
        self.admin.save()

        self.project_user = create_test_user(name='project_user', password='pw')
        self.project = project_creation("testproj", TEST_INDEX, self.user)
        self.project.users.add(self.project_user)
        self.project.users.add(self.user)

        self.client = APIClient()
        self.client.login(username='project_user', password='pw')

        self.scroll_url = reverse(f"{VERSION_NAMESPACE}:project-scroll", kwargs={"project_pk": self.project.id})


    def test_that_only_owner_can_access_project(self):
        self.client.login(username='unowned_user', password='pw')
        response = self.client.post(self.scroll_url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        print_output("test_that_only_owner_can_access_project", 406)


    def test_full_index_scrolling(self):
        response = self.client.post(self.scroll_url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        document_count = len(response.data["documents"])
        total_documents = response.data["total_documents"]
        document_counter = document_count  # Initialise counter with the amount of the first response.

        try_counter = 0
        try_limit = 25
        while document_count != 0:
            if try_counter != try_limit:
                response = self.client.post(self.scroll_url, data={"scroll_id": response.data["scroll_id"]}, format="json")
                self.assertTrue(response.status_code == status.HTTP_200_OK)
                document_count = len(response.data["documents"])
                document_counter += document_count
                try_counter += 1
            else:
                raise Exception("Infinite looping in Scroll API.")

        self.assertTrue(total_documents == document_counter)
        print_output("test_full_index_scrolling", 200)


    def test_basic_functionality(self):
        response = self.client.post(self.scroll_url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        for key in ["scroll_id", "documents", "total_documents", "returned_count"]:
            self.assertTrue(key in response.data)
        self.assertTrue(response.data["total_documents"] != response.data["returned_count"])
        self.assertTrue(response.data["total_documents"] > response.data["returned_count"])

        scrolling = self.client.post(self.scroll_url, data={"scroll_id": response.data["scroll_id"]}, format="json")
        self.assertTrue(scrolling.status_code == status.HTTP_200_OK)
        for key in ["scroll_id", "documents", "total_documents", "returned_count"]:
            self.assertTrue(key in scrolling.data)
        self.assertTrue(scrolling.data["total_documents"] != scrolling.data["returned_count"])
        self.assertTrue(scrolling.data["total_documents"] > scrolling.data["returned_count"])
        print_output("test_basic_functionality", 200)


    def test_that_query_parameter_limits_search_range(self):
        response = self.client.post(self.scroll_url, data={
            "with_meta": False, "fields": [TEST_FIELD], "query": {
                "query": {"term": {"comment_subject.keyword": "juss"}}
            }
        }, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(len(response.data["documents"]) < 100)
        print_output("test_that_query_parameter_limits_search_range", 200)


    def test_that_fields_parameter_returns_only_selected_fields(self):
        response = self.client.post(self.scroll_url, data={"documents_size": 1, "with_meta": False, "fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        document = response.data["documents"][0]
        keys = list(document.keys())
        self.assertTrue(len(keys) == 1 and keys[0] == TEST_FIELD)
        print_output("test_that_fields_parameter_returns_only_selected_fields", 200)


    def test_that_false_indices_are_handled_properly(self):
        response = self.client.post(self.scroll_url, data={"documents_size": 1, "with_meta": True, "indices": ["an_european_or_african_swallow"]}, format="json")
        self.assertTrue((response.status_code == status.HTTP_400_BAD_REQUEST))
        print_output("test_that_false_indices_are_handled_properly", 400)


    def test_that_false_fields_are_handled_properly(self):
        """
        When the field doesn't exist, it just returns an empty document.
        """
        response = self.client.post(self.scroll_url, data={"documents_size": 1, "with_meta": False, "fields": ["beware_of_tim_the_enchanter"]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        document = response.data["documents"][0]
        self.assertFalse(document)
        print_output("test_that_false_fields_are_handled_properly", 200)


    def test_that_initial_scroll_and_continuation_have_different_values(self):
        response = self.client.post(self.scroll_url, data={"documents_size": 1, "with_meta": True, "fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        first_id = response.data["documents"][0]["_id"]
        continuation_scroll = self.client.post(self.scroll_url, data={"scroll_id": response.data["scroll_id"], "with_meta": True}, format="json")
        second_id = continuation_scroll.data["documents"][0]["_id"]
        self.assertTrue(continuation_scroll.status_code == status.HTTP_200_OK)
        self.assertTrue(first_id != second_id)
        print_output("test_that_initial_scroll_and_continuation_have_different_values", 200)


    def test_that_size_parameter_limits_returned_document_count(self):
        response = self.client.post(self.scroll_url, data={"documents_size": 3}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(len(response.data["documents"]) == 3)
        print_output("test_that_size_parameter_limits_returned_document_count", 200)


    def test_aggregations_being_thrown_away_turning_serialization(self):
        response = self.client.post(self.scroll_url, data={
            "query": {**EMPTY_QUERY, **{"aggs": {"genres": {"terms": {"field": "genre"}}}}}
        }, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        print_output("test_aggregations_being_thrown_away_turning_serialization", 200)


    def test_that_all_users_have_access_to_scrolling(self):
        self.client.login(username="admin", password="pw")
        response = self.client.post(self.scroll_url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        self.client.login(username="user", password="pw")
        response = self.client.post(self.scroll_url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        print_output("test_that_all_users_have_access_to_scrolling", 200)
