# Create your tests here.
import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (TEST_FIELD, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation
from toolkit.topic_analyzer.models import Cluster, ClusteringResult


@override_settings(CELERY_ALWAYS_EAGER=True)
class TopicAnalyzerTests(APITransactionTestCase):
    """
    Because cluster training is done using the on_commit hook because of its current architecture,
    this test module is a bit different compared to the other application, for using APITransactionTestCase
    instead of the APITestCase, which has setUpTestData() as a class function.
    """


    def _train_topic_cluster(self) -> int:
        response = self.client.post(self.clustering_url, format="json", data=self.payload)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("_train_topic_cluster", 201)
        return response.data["id"]


    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.admin_user = create_test_user("admin", "", "pw")
        self.admin_user.is_superuser = True
        self.admin_user.save()

        self.project = project_creation("projectAnalyzerProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.project.users.add(self.admin_user)
        self.clustering_url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-list", kwargs={"project_pk": self.project.pk})
        self.payload = {
            "description": "TopicCluster",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "document_limit": 500,
            "num_topics": 50,
            "num_cluster": 10
        }

        self.client.login(username='user', password='pw')
        self.clustering_id = self._train_topic_cluster()


    def tearDown(self) -> None:
        ClusteringResult.objects.all().delete()
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def test_access_to_detail_page(self):
        url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-detail", kwargs={"project_pk": self.project.pk, "pk": self.clustering_id})
        response = self.client.get(url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        print_output("test_access_to_detail_page", 200)


    def test_training_cluster_with_embedding(self):
        # Payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "fields": [TEST_FIELD],
            "indices": [{"name": self.test_index_name}],
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 300
        }
        embeddings_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_training_cluster_with_embedding:response.data", response.data)

        # Train the actual cluster.
        payload = {**self.payload, "embedding": response.data["id"]}
        response = self.client.post(self.clustering_url, format="json", data=payload)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("_train_topic_cluster", 201)

        self.assertTrue("tasks" in response.data)
        self.assertEqual(len(response.data["tasks"]), 1)


    def test_cluster_with_indices_field(self):
        """
        After the commit that changes index handling, it's safer to explicitly test for this field.
        """
        payload = {
            "description": "TopicCluster",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.clustering_url, format="json", data=payload)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_cluster_with_indices_field", 201)


    def test_access_to_cluster_page_and_content_of_clusters(self):
        url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-view-clusters", kwargs={"project_pk": self.project.pk, "pk": self.clustering_id})
        response = self.client.get(url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["cluster_count"] == len(response.data["clusters"]))

        for cluster in response.data["clusters"]:
            # Check if the fields are filled with content
            self.assertTrue(cluster["documents"])
            self.assertTrue(cluster["url"])

            # Check average similarity
            self.assertTrue(round(cluster["average_similarity"], 5) <= 1.0)

            # Count should be handled by the serializer function.
            self.assertTrue(cluster["document_count"] == len(cluster["documents"]))

            # Check if the URL handling for singular clusters is actually correct.
            cluster_response = self.client.get(cluster["url"])
            self.assertTrue(cluster_response.status_code == status.HTTP_200_OK)

        print_output("test_access_to_cluster_page_and_content_of_clusters", 200)


    def test_singular_cluster_detail_page(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()

        cluster_detail_url = reverse(f"{VERSION_NAMESPACE}:cluster-detail", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        cluster_details = self.client.get(cluster_detail_url)
        self.assertTrue(cluster_details.status_code == status.HTTP_200_OK)

        self.assertTrue("significant_words" in cluster_details.data)
        self.assertTrue("documents" in cluster_details.data)

        for document in cluster_details.data["documents"]:
            self.assertTrue("index" in document)
            self.assertTrue("id" in document)
            self.assertTrue("content" in document)

            # Check that the field key exists inside the content window.
            document_content = document["content"]
            keys = list(document_content.keys())
            self.assertTrue(len(keys) > 0)

        print_output("test_singular_cluster_detail_page", 201)


    def test_more_like_cluster_functionality(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        url = reverse(f"{VERSION_NAMESPACE}:cluster-more-like-cluster", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        for mlt in response.data:
            self.assertTrue(TEST_FIELD in mlt)
            self.assertTrue(mlt[TEST_FIELD])

        print_output("test_more_like_cluster_functionality", 200)


    def test_more_like_cluster_with_size_parameter(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        url = reverse(f"{VERSION_NAMESPACE}:cluster-more-like-cluster", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, data={"size": 1}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(len(response.data) == 1)
        print_output("test_more_like_cluster_with_size_parameter", 200)


    def test_more_like_cluster_with_meta_information(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        url = reverse(f"{VERSION_NAMESPACE}:cluster-more-like-cluster", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, data={"include_meta": True}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        for mlt in response.data:
            self.assertTrue("_index" in mlt)
            self.assertTrue("_id" in mlt)
            self.assertTrue("_source" in mlt)
            self.assertTrue(TEST_FIELD in mlt["_source"])

        print_output("test_more_like_cluster_with_meta_information", 200)


    def test_ignore_and_delete_functionality_of_singular_clusters(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        document_ids = json.loads(singular_cluster.document_ids)

        url = reverse(f"{VERSION_NAMESPACE}:cluster-ignore-and-delete", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, data={}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(Cluster.objects.filter(pk=singular_cluster.pk).count() == 0)  # Check that the cluster doesn't exist anymore.

        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        ignored_ids = json.loads(clustering.ignored_ids)
        self.assertTrue(ignored_ids)
        self.assertTrue(len(document_ids) == len(ignored_ids))


    def test_tagging_a_cluster_functionality(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        document_ids = json.loads(singular_cluster.document_ids)

        url = reverse(f"{VERSION_NAMESPACE}:cluster-tag-cluster", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        payload = {
            "fact": "TEST_FACT",
            "str_val": "TEST_CONTENT",
            "doc_path": TEST_FIELD
        }

        response = self.client.post(url, format="json", data=payload)
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        ed = ElasticDocument("_all")
        for document_id in document_ids:
            document = ed.get(document_id)
            facts = document["_source"].get("texta_facts", [])

            fact_names = [fact["fact"] for fact in facts]
            self.assertTrue("TEST_FACT" in fact_names)

            fact_values = [fact["str_val"] for fact in facts]
            self.assertTrue("TEST_CONTENT" in fact_values)

        print_output("test_tagging_a_cluster_functionality", 200)


    def test_updating_singular_cluster_information(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        document_ids = json.loads(singular_cluster.document_ids)
        document_to_keep = document_ids[-1]

        url = reverse(f"{VERSION_NAMESPACE}:cluster-detail", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.patch(url, format="json", data={
            "document_ids": [document_to_keep]
        })
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(len(response.data["documents"]) == 1)
        self.assertTrue(response.data["documents"][0]["id"] == document_to_keep)
        print_output("test_updating_singular_cluster_information", 200)


    def test_user_and_admin_access_to_endpoints(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()

        for user in [{"username": "admin", "password": "pw"}, {"username": "user", "password": "pw"}]:
            self.client.login(**user)
            # Clustering LIST View
            response = self.client.get(self.clustering_url)
            self.assertTrue(response.status_code == status.HTTP_200_OK)

            # Clustering DETAIL View
            url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-detail", kwargs={"project_pk": self.project.pk, "pk": clustering.pk})
            response = self.client.get(url)
            self.assertTrue(response.status_code == status.HTTP_200_OK)

            # Cluster DETAIL View
            url = reverse(f"{VERSION_NAMESPACE}:cluster-detail", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
            response = self.client.get(url)
            self.assertTrue(response.status_code == status.HTTP_200_OK)

        print_output("test_user_and_admin_access_to_endpoints", 200)


    def test_adding_documents_to_cluster(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()

        helper_cluster = clustering.cluster_result.last()
        legit_ids_to_add = json.loads(helper_cluster.document_ids)

        url = reverse(f"{VERSION_NAMESPACE}:cluster-add-documents", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, format="json", data={"ids": legit_ids_to_add})

        updated_cluster = clustering.cluster_result.first()
        for doc_id in legit_ids_to_add:
            self.assertTrue(doc_id in json.loads(updated_cluster.document_ids))


    def test_removing_documents_from_cluster(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()

        ids_to_remove = json.loads(singular_cluster.document_ids)[-3:]
        url = reverse(f"{VERSION_NAMESPACE}:cluster-remove-documents", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})
        response = self.client.post(url, format="json", data={"ids": ids_to_remove})
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        singular_cluster = clustering.cluster_result.first()
        for doc_id in json.loads(singular_cluster.document_ids):
            self.assertTrue(doc_id not in ids_to_remove)

        print_output("test_removing_documents_from_cluster", 200)


    def test_transferring_documents_from_one_cluster_to_another(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        from_cluster = clustering.cluster_result.first()
        to_cluster = clustering.cluster_result.last()
        self.assertTrue(from_cluster.pk != to_cluster.pk)

        ids = json.loads(from_cluster.document_ids)
        url = reverse(f"{VERSION_NAMESPACE}:cluster-transfer-documents", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": from_cluster.pk})
        response = self.client.post(url, format="json", data={"ids": ids, "receiving_cluster_id": to_cluster.pk})
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        from_cluster = clustering.cluster_result.first()
        from_ids = json.loads(from_cluster.document_ids)

        to_cluster = clustering.cluster_result.last()
        to_ids = json.loads(to_cluster.document_ids)

        for doc_id in ids:
            self.assertTrue(doc_id not in from_ids)
            self.assertTrue(doc_id in to_ids)


    def test_cluster_exist_validation_for_transferring_endpoint(self):
        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        singular_cluster = clustering.cluster_result.first()
        url = reverse(f"{VERSION_NAMESPACE}:cluster-transfer-documents", kwargs={"project_pk": self.project.pk, "topic_analyzer_pk": clustering.pk, "pk": singular_cluster.pk})

        response = self.client.post(url, format="json", data={"ids": ["wrong, sample id"], "receiving_cluster_id": 1000})
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_cluster_deletion_on_clustering_deletion(self):
        clustering_id = self._train_topic_cluster()
        clustering = ClusteringResult.objects.get(pk=clustering_id)
        cluster_ids = [cluster.id for cluster in clustering.cluster_result.all()]

        url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-detail", kwargs={"project_pk": self.project.pk, "pk": clustering_id})
        response = self.client.delete(url)
        self.assertTrue(response.status_code == status.HTTP_204_NO_CONTENT)

        clusters = Cluster.objects.filter(id__in=cluster_ids)
        self.assertTrue(clusters.count() == 0)
        print_output("test_cluster_deletion_on_clustering_deletion", 204)


    def test_updating_clustering_instances_stop_words(self):
        stop_words = ["ja", "siis", "kui", "ka"]
        url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-detail", kwargs={"project_pk": self.project.pk, "pk": self.clustering_id})
        response = self.client.patch(url, data={"stop_words": stop_words}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)

        clustering = ClusteringResult.objects.get(pk=self.clustering_id)
        stored_stop_words = json.loads(clustering.stop_words)
        self.assertTrue(sorted(stop_words) == sorted(stored_stop_words))
        print_output("test_updating_clustering_instances_stop_words", 201)


    def test_that_clusters_dont_contain_duplicate_document_ids(self):
        url = reverse(f"{VERSION_NAMESPACE}:topic_analyzer-list", kwargs={"project_pk": self.project.pk})
        payload = {
            "description": "TopicCluster",
            "fields": ["comment_subject", "comment_content"],
            "vectorizer": "TfIdf Vectorizer"
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        clustering = ClusteringResult.objects.get(pk=response.data["id"])
        clusters = clustering.cluster_result.all()

        ids = []

        for cluster in clusters:
            document_ids = json.loads(cluster.document_ids)
            # Check for one document appearing multiple times in the cluster.
            self.assertTrue(len(document_ids) == len(set(document_ids)))
            for idx in document_ids:
                ids.append(idx)

        self.assertTrue(len(ids) == len(set(ids)))
