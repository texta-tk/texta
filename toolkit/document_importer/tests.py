# Create your tests here.
from django.urls import reverse
from elasticsearch import NotFoundError
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.elastic.core import ElasticCore
from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class DocumentImporterAPITestCase(APITestCase):

    def setUp(self):
        self.user = create_test_user('first_user', 'my@email.com', 'pw')
        self.project = project_creation("DocumentImporterAPI", TEST_INDEX, self.user)

        self.validation_project = project_creation("validation_project", "random_index_name", self.user)
        self.project.users.add(self.user)
        self.document_id = 41489489465
        self.source = {"hello": "world"}
        self.document = {"_index": TEST_INDEX, "_type": TEST_INDEX, "_id": self.document_id, "_source": self.source}

        self.client.login(username='first_user', password='pw')
        self._check_inserting_documents()


    def _check_inserting_documents(self):
        url = reverse("v1:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [self.document]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        ec = ElasticCore()
        document = ec.es.get(id=self.document_id, index=TEST_INDEX, doc_type=TEST_INDEX)
        self.assertTrue(document["_source"])
        print_output("_check_inserting_documents:response.data", response.data)


    def tearDown(self) -> None:
        ec = ElasticCore()
        ec.es.delete(index=TEST_INDEX, id=self.document_id, doc_type=TEST_INDEX, ignore=[400, 404])


    def test_adding_documents_to_false_project(self):
        url = reverse("v1:document_import", kwargs={"pk": self.validation_project.pk})
        response = self.client.post(url, data={"documents": [self.document]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        print_output("test_adding_documents_to_false_project:response.data", response.data)


    def test_adding_documents_to_false_index(self):
        url = reverse("v1:document_import", kwargs={"pk": self.project.pk})
        index_name = "wrong_index"
        response = self.client.post(url, data={"documents": [{"_index": index_name, "_type": index_name, "_source": self.document}]}, format="json")
        try:
            ec = ElasticCore()
            ec.es.get(id=self.document_id, index=index_name, doc_type=index_name)
        except NotFoundError:
            print_output("test_adding_documents_to_false_index:response.data", response.data)
        else:
            raise Exception("Elasticsearch indexed a document it shouldn't have!")


    def test_updating_document(self):
        url = reverse("v1:document_instance", kwargs={"pk": self.project.pk, "index": TEST_INDEX, "document_id": self.document_id})
        response = self.client.patch(url, data={"hello": "night", "goodbye": "world"})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        ec = ElasticCore()
        document = ec.es.get(index=TEST_INDEX, doc_type=TEST_INDEX, id=self.document_id)["_source"]
        self.assertTrue(document["hello"] == "night" and document["goodbye"] == "world")
        print_output("test_updating_document:response.data", response.data)


    def test_deleting_document(self):
        url = reverse("v1:document_instance", kwargs={"pk": self.project.pk, "index": TEST_INDEX, "document_id": self.document_id})
        response = self.client.delete(url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        try:
            ec = ElasticCore()
            ec.es.get(id=self.document_id, index=TEST_INDEX, doc_type=TEST_INDEX)
        except NotFoundError:
            print_output("test_deleting_document:response.data", response.data)
        else:
            raise Exception("Elasticsearch didnt delete a document it should have!")


    def test_unauthenticated_access(self):
        self.client.logout()
        url = reverse("v1:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [self.document]}, format="json")
        print_output("test_unauthenticated_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_adding_document_without_specified_index(self):
        from toolkit.document_importer.views import DocumentImportView
        sample_id = 65959645
        url = reverse("v1:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [{"_source": self.source, "_id": sample_id}]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        ec = ElasticCore()
        normalized_project_title = DocumentImportView.get_new_index_name(self.project.title)
        document = ec.es.get(id=sample_id, index=normalized_project_title, doc_type=normalized_project_title)

        ec.delete_index(normalized_project_title)  # Cleanup

        self.assertTrue(document["_source"])
        self.assertTrue(response.data["created_indices"][0] == normalized_project_title)
        self.assertTrue(self.project.indices.filter(name=normalized_project_title).exists())
        print_output("test_adding_document_without_specified_index:response.data", response.data)

