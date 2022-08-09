# Create your tests here.
import random
import uuid

from django.urls import reverse
from elasticsearch import NotFoundError
from elasticsearch_dsl import Q, Search
from rest_framework import status
from rest_framework.test import APITestCase
from texta_elastic.core import ElasticCore

from toolkit.elastic.index.models import Index
from toolkit.helper_functions import reindex_test_dataset, set_core_setting
from toolkit.test_settings import VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class DocumentImporterAPITestCase(APITestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('first_user', 'my@email.com', 'pw')
        self.project = project_creation("DocumentImporterAPI", self.test_index_name, self.user)

        self.validation_project = project_creation("validation_project", "random_index_name", self.user)

        self.document_id = random.randint(10000000, 90000000)
        self.uuid = uuid.uuid1()
        self.source = {"hello": "world", "uuid": self.uuid}
        self.document = {"_index": self.test_index_name, "_id": self.document_id, "_source": self.source}

        self.target_field_random_key = uuid.uuid1()
        self.target_field = f"{self.target_field_random_key}_court_case"
        self.ec = ElasticCore()

        self.client.login(username='first_user', password='pw')
        self._check_inserting_documents()


    def _check_inserting_documents(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [self.document], "split_text_in_fields": []}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        document = self.ec.es.get(id=self.document_id, index=self.test_index_name)
        print_output("_check_inserting_documents:response.data", response.data)
        self.assertTrue(document["_source"])


    def tearDown(self) -> None:
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        query = Search().query(Q("exists", field=self.target_field)).to_dict()
        self.ec.es.delete_by_query(index="*", body=query, wait_for_completion=True)


    def test_adding_documents_to_false_project(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.validation_project.pk})
        self.validation_project.users.remove(self.user)
        response = self.client.post(url, data={"documents": [self.document]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        print_output("test_adding_documents_to_false_project:response.data", response.data)


    def test_adding_documents_to_false_index(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        index_name = "wrong_index"
        response = self.client.post(url, data={"documents": [{"_index": index_name, "_source": self.document}]}, format="json")
        try:
            self.ec.es.get(id=self.document_id, index=index_name)
        except NotFoundError:
            print_output("test_adding_documents_to_false_index:response.data", response.data)
        else:
            raise Exception("Elasticsearch indexed a document it shouldn't have!")


    def test_updating_document(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_instance", kwargs={"pk": self.project.pk, "index": self.test_index_name, "document_id": self.document_id})
        response = self.client.patch(url, data={"hello": "night", "goodbye": "world"})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        document = self.ec.es.get(index=self.test_index_name, id=self.document_id)["_source"]
        self.assertTrue(document["hello"] == "night" and document["goodbye"] == "world")
        print_output("test_updating_document:response.data", response.data)


    def test_deleting_document(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_instance", kwargs={"pk": self.project.pk, "index": self.test_index_name, "document_id": self.document_id})
        response = self.client.delete(url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        try:
            self.ec.es.get(id=self.document_id, index=self.test_index_name)
        except NotFoundError:
            print_output("test_deleting_document:response.data", response.data)
        else:
            raise Exception("Elasticsearch didnt delete a document it should have!")


    def test_unauthenticated_access(self):
        self.client.logout()
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [self.document]}, format="json")
        print_output("test_unauthenticated_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_adding_document_without_specified_index_and_that_index_is_added_into_project(self):
        from toolkit.elastic.document_importer.views import DocumentImportView
        sample_id = 65959645
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [{"_source": self.source, "_id": sample_id}]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        normalized_project_title = DocumentImportView.get_new_index_name(self.project.pk)
        document = self.ec.es.get(id=sample_id, index=normalized_project_title)

        self.ec.delete_index(normalized_project_title)  # Cleanup

        self.assertTrue(document["_source"])
        self.assertTrue(self.project.indices.filter(name=normalized_project_title).exists())

        # Test that usernames are added automatically into the newly created index.
        self.assertTrue(Index.objects.filter(name=normalized_project_title, added_by=self.user.username).exists())

        print_output("test_adding_document_without_specified_index_and_that_index_is_added_into_project:response.data", response.data)


    def test_updating_non_existing_document(self):
        sample_id = "random_id"
        url = reverse(f"{VERSION_NAMESPACE}:document_instance", kwargs={"pk": self.project.pk, "index": self.test_index_name, "document_id": sample_id})
        response = self.client.patch(url, data={"hello": "world"}, format="json")
        print_output("test_updating_non_existing_document:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_404_NOT_FOUND)


    def test_deleting_non_existing_document(self):
        sample_id = "random_id"
        url = reverse(f"{VERSION_NAMESPACE}:document_instance", kwargs={"pk": self.project.pk, "index": self.test_index_name, "document_id": sample_id})
        response = self.client.delete(url, data={"hello": "world"}, format="json")
        print_output("test_deleting_non_existing_document:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_404_NOT_FOUND)


    def test_that_specified_field_is_being_split(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        uuid = "456694-asdasdad4-54646ad-asd4a5d"
        response = self.client.post(
            url,
            format="json",
            data={
                "split_text_in_fields": [self.target_field],
                "documents": [{
                    "_index": self.test_index_name,
                    "_source": {
                        self.target_field: "Paradna on kohtu alla antud kokkuleppe alusel selles, et tema, 25.10.2003 kell 00.30 koos,...",
                        "uuid": uuid
                    }
                }]},
        )
        print_output("test_that_specified_field_is_being_split:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        documents = self.ec.es.search(index=self.test_index_name, body={"query": {"term": {"uuid.keyword": uuid}}})
        document = documents["hits"]["hits"][0]
        self.assertTrue(document)
        self.assertTrue(document["_source"])
        self.assertTrue("page" in document["_source"])


    def test_that_wrong_field_value_will_skip_splitting(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        uuid = "Adios"
        response = self.client.post(
            url,
            format="json",
            data={
                "documents": [{
                    "_index": self.test_index_name,
                    "_source": {
                        self.target_field: "Paradna on kohtu alla antud kokkuleppe alusel selles, et tema, 25.10.2003 kell 00.30 koos,...",
                        "uuid": uuid
                    }
                }]},
        )
        print_output("test_that_empty_field_value_will_skip_splitting:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        documents = self.ec.es.search(index=self.test_index_name, body={"query": {"term": {"uuid.keyword": uuid}}})
        document = documents["hits"]["hits"][0]
        self.assertTrue(document)
        self.assertTrue(document["_source"])
        self.assertTrue("page" not in document["_source"])


    def test_splitting_behaviour_with_empty_list_as_input(self):
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        uuid = "adasdasd-5g465s-fa4s69f4a8s97-a4das9f4"
        response = self.client.post(
            url,
            format="json",
            data={
                "split_text_in_fields": [],
                "documents": [{
                    "_index": self.test_index_name,
                    "_source": {
                        self.target_field: "Paradna on kohtu alla antud kokkuleppe alusel selles, et tema, 25.10.2003 kell 00.30 koos,...",
                        "uuid": uuid
                    }
                }]},
        )
        print_output("test_splitting_behaviour_with_empty_list_as_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        documents = self.ec.es.search(index=self.test_index_name, body={"query": {"term": {"uuid.keyword": uuid}}})
        document = documents["hits"]["hits"][0]
        self.assertTrue(document)
        self.assertTrue(document["_source"])
        self.assertTrue("page" not in document["_source"])


    def test_that_indexes_do_rollover_after_a_certain_count(self):
        set_core_setting("TEXTA_ES_MAX_DOCS_PER_INDEX", "50")
        url = reverse(f"{VERSION_NAMESPACE}:document_import", kwargs={"pk": self.project.pk})
        response = self.client.post(url, data={"documents": [{"_source": {"value": i}} for i in range(51)], "split_text_in_fields": []}, format="json")
        print_output("test_that_indexes_do_rollover_after_a_certain_count:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        # Send a batch for the second time to see if the documents rolled over properly.
        clean_up_container = ["texta-1-import-project-1"]
        for i in range(1, 12):
            response = self.client.post(url, data={"documents": [{"_source": {"value": i}} for i in range(51)], "split_text_in_fields": []}, format="json")

            self.assertTrue(response.status_code == status.HTTP_200_OK)
            if i == 1:
                self.assertTrue(self.project.indices.filter(name="texta-1-import-project-1").exists())
            else:
                # i-1 because the first request doesn't add the rollover index counter.
                rollover_index_name = f"texta-1-import-project-1-{i - 1}"
                self.assertTrue(self.project.indices.filter(name=rollover_index_name).exists())
                clean_up_container.append(rollover_index_name)

        # Cleanup
        self.ec.delete_index(index=",".join(clean_up_container))
