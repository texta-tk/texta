# Create your tests here.
import json

from django.urls import reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from texta_elastic.core import ElasticCore

from toolkit.annotator.models import Annotator
from toolkit.elastic.index.models import Index
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import TEXTA_ANNOTATOR_KEY
from toolkit.test_settings import TEST_FIELD, TEST_MATCH_TEXT, TEST_QUERY
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class BinaryAnnotatorTests(APITestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.secondary_index = reindex_test_dataset()
        self.index, is_created = Index.objects.get_or_create(name=self.secondary_index)
        self.user = create_test_user('annotator', 'my@email.com', 'pw')
        self.user2 = create_test_user('annotator2', 'test@email.com', 'pw2')
        self.project = project_creation("taggerTestProject", self.test_index_name, self.user)
        self.project.indices.add(self.index)
        self.project.users.add(self.user)
        self.project.users.add(self.user2)

        self.client.login(username='annotator', password='pw')
        self.ec = ElasticCore()

        self.list_view_url = reverse("v2:annotator-list", kwargs={"project_pk": self.project.pk})
        self.annotator = self._create_annotator()
        self.pull_document_url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})


    def test_all(self):
        self.run_binary_annotator_group()
        self.run_create_annotator_for_multi_user()
        self.run_pulling_document()
        self.run_binary_annotation()
        self.run_that_query_limits_pulled_document()
        doc_id_with_comment = self.run_adding_comment_to_document()
        self.run_pulling_comment_for_document(doc_id_with_comment)
        self.run_check_proper_skipping_functionality()
        self.run_annotating_to_the_end()
        self.run_create_labelset()


    def _create_annotator(self):
        payload = {
            "description": "Random test annotation.",
            "indices": [{"name": self.test_index_name}, {"name": self.secondary_index}],
            "query": json.dumps(TEST_QUERY),
            "fields": ["comment_content", TEST_FIELD],
            "target_field": "comment_content",
            "annotation_type": "binary",
            "annotating_users": ["annotator"],
            "binary_configuration": {
                "fact_name": "TOXICITY",
                "pos_value": "DO_DELETE",
                "neg_value": "SAFE"
            }
        }
        response = self.client.post(self.list_view_url, data=payload, format="json")
        print_output("_create_annotator:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        total_count = self.ec.es.count(index=f"{self.test_index_name},{self.secondary_index}").get("count", 0)
        self.assertTrue(total_count > response.data["total"])
        return response.data


    def _pull_random_document(self):
        url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        response = self.client.post(url, format="json")
        return response.data

    def run_binary_annotator_group(self):
        annotator_children = []
        for i in range(2):
            child = self._create_annotator()
            annotator_children.append(child["id"])
        group_url = reverse("v2:annotator_groups-list", kwargs={"project_pk": self.project.pk})
        group_payload = {
            "parent": self.annotator["id"],
            "children": annotator_children
        }
        group_response = self.client.post(group_url, data=group_payload, format="json")
        print_output("run_binary_annotator_group:response.status", group_response.status_code)
        self.assertTrue(group_response.status_code == status.HTTP_201_CREATED)


    def run_create_annotator_for_multi_user(self):
        payload = {
            "description": "Multi user annotation.",
            "indices": [{"name": self.test_index_name}, {"name": self.secondary_index}],
            "query": json.dumps(TEST_QUERY),
            "fields": ["comment_content", TEST_FIELD],
            "target_field": "comment_content",
            "annotation_type": "binary",
            "annotating_users": ["annotator", "annotator2"],
            "binary_configuration": {
                "fact_name": "TOXICITY",
                "pos_value": "DO_DELETE",
                "neg_value": "SAFE"
            }
        }
        response = self.client.post(self.list_view_url, data=payload, format="json")
        print_output("create_annotator_for_multi_user:response.status", response.status_code)
        print_output("create_annotator_for_multi_user:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        for d in response.data["annotator_users"]:
            self.assertIn(d["username"], {str(self.user), str(self.user2)})

        total_count = self.ec.es.count(index=f"{self.test_index_name},{self.secondary_index}").get("count", 0)
        self.assertTrue(total_count > response.data["total"])


    def run_binary_annotation(self):
        annotation_url = reverse("v2:annotator-annotate-binary", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        print_output("run_binary_annotation:annotation_url", annotation_url)
        annotation_payloads = []
        for i in range(2):
            random_document = self._pull_random_document()
            annotation_payloads.append(
                {"index": random_document["_index"], "document_id": random_document["_id"], "doc_type": "_doc", "annotation_type": "pos"}
            )
        print_output("annotation_document_before_0", annotation_payloads[0]['document_id'])
        print_output("annotation_document_before_1", annotation_payloads[1]['document_id'])
        while annotation_payloads[0]['document_id'] == annotation_payloads[1]['document_id']:
            random_document = self._pull_random_document()
            annotation_payloads[1] = {"index": random_document["_index"], "document_id": random_document["_id"], "doc_type": "_doc", "annotation_type": "pos"}
        print_output("run_binary_annotation:annotation_payloads", annotation_payloads)
        for index_count, payload in enumerate(annotation_payloads):
            print_output(f"run_binary_annotation:annotation_payload{index_count}", payload['document_id'])
            annotation_response = self.client.post(annotation_url, data=payload, format="json")
            # Test for response success.
            print_output("run_binary_annotation:response.status", annotation_response.status_code)
            self.assertTrue(annotation_response.status_code == status.HTTP_200_OK)

            # Test that progress is updated properly.
            model_object = Annotator.objects.get(pk=self.annotator["id"])
            print_output("run_binary_annotation:annotator_model_obj", model_object.annotated)
            print_output("run_binary_annotation:binary_index_count", index_count)
            self.assertTrue(model_object.annotated == index_count + 1)

            # Check that document was actually edited.
            es_doc = self.ec.es.get(index=payload["index"], id=payload["document_id"])["_source"]
            facts = es_doc["texta_facts"]
            self.assertTrue(model_object.binary_configuration.fact_name in [fact["fact"] for fact in facts])
            if payload["annotation_type"] == "pos":
                self.assertTrue(model_object.binary_configuration.pos_value in [fact["str_val"] for fact in facts])
            elif payload["annotation_type"] == "neg":
                self.assertTrue(model_object.binary_configuration.neg_value in [fact["str_val"] for fact in facts])


    def run_annotating_to_the_end(self):
        model_object = Annotator.objects.get(pk=self.annotator["id"])
        total = model_object.total
        annotated = model_object.annotated
        skipped = model_object.skipped
        validated = model_object.validated

        annotation_url = reverse("v2:annotator-annotate-binary", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})

        for i in range(total - annotated - skipped - validated):
            random_document = self._pull_random_document()
            payload = {"annotation_type": "pos", "document_id": random_document["_id"], "index": random_document["_index"]}
            annotation_response = self.client.post(annotation_url, data=payload, format="json")
            self.assertTrue(annotation_response.status_code == status.HTTP_200_OK)

        # At this point all the documents should be done.
        random_document = self._pull_random_document()
        self.assertTrue(random_document["detail"] == 'No more documents left!')


    def run_create_labelset(self):
        payload = {
            "indices": [self.test_index_name, self.secondary_index],
            "fact_names": ["TOXICITY"],
            "value_limit": 30,
            "category": "test_labelset",
            "values": ["first_value", "second_value"]
        }
        response = self.client.post(reverse("v2:labelset-list", kwargs={"project_pk": self.project.pk}), data=payload, format="json")
        print_output("run_create_labelset:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def run_pulling_comment_for_document(self, document_id):
        url = reverse("v2:annotator-get-comments", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        payload = {"document_id": document_id}
        response = self.client.post(url, data=payload, format="json")
        print_output("run_pulling_comment_for_document:response.data", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["count"] == 1)

        comment = response.data["results"][0]
        self.assertTrue(comment.get("text", ""))
        self.assertTrue(comment.get("document_id", "") == document_id)
        self.assertTrue(comment.get("user", "") == self.user.username)
        self.assertTrue(comment.get("created_at", ""))


    def run_pulling_document(self):
        url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        # Test pulling documents several times as that will be a common behavior.
        for i in range(3):
            response = self.client.post(url, format="json")
            print_output("run_pulling_document:response.status", response.status_code)
            self.assertTrue(response.status_code == status.HTTP_200_OK)
            self.assertTrue(response.data.get("_id", None))
            self.assertTrue(response.data.get("_source", None))
            self.assertTrue(response.data.get("_index", None))
            self.assertTrue(response.data["_source"].get(TEST_FIELD), None)


    def run_adding_comment_to_document(self):
        random_document = self._pull_random_document()
        document_id = random_document["_id"]
        url = reverse("v2:annotator-add-comment", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        payload = {
            "document_id": document_id,
            "text": "Ah, miks sa teed nii!?"
        }
        response = self.client.post(url, data=payload, format="json")
        print_output("run_adding_comment_to_document:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        return document_id


    def run_that_query_limits_pulled_document(self):
        random_document = self._pull_random_document()
        content = random_document["_source"]
        print_output("run_that_query_limits_pulled_document:source", content)
        self.assertTrue(TEST_MATCH_TEXT in content.get(TEST_FIELD, ""))


    def run_check_proper_skipping_functionality(self):
        random_document = self._pull_random_document()
        skip_url = reverse("v2:annotator-skip-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        doc_index = random_document["_index"]
        doc_id = random_document["_id"]
        response = self.client.post(skip_url, data={"document_id": doc_id, "index": doc_index}, format="json")
        print_output("run_check_proper_skipping_functionality:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        elastic_doc = self.ec.es.get(index=doc_index, id=doc_id)

        annotator_list = elastic_doc["_source"][TEXTA_ANNOTATOR_KEY]
        annotator_dict = [dictionary for dictionary in annotator_list if dictionary["job_id"] == self.annotator["id"]][0]
        self.assertTrue(annotator_dict["skipped_timestamp_utc"])


    def run_that_double_skipped_document_wont_be_counted(self):
        pass

@override_settings(CELERY_ALWAYS_EAGER=True)
class EntityAnnotatorTests(APITestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.secondary_index = reindex_test_dataset()
        self.index, is_created = Index.objects.get_or_create(name=self.secondary_index)
        self.user = create_test_user('annotator', 'my@email.com', 'pw')
        self.user2 = create_test_user('annotator2', 'test@email.com', 'pw2')
        self.project = project_creation("entityTestProject", self.test_index_name, self.user)
        self.project.indices.add(self.index)
        self.project.users.add(self.user)
        self.project.users.add(self.user2)

        self.client.login(username='annotator', password='pw')
        self.ec = ElasticCore()

        self.list_view_url = reverse("v2:annotator-list", kwargs={"project_pk": self.project.pk})
        self.annotator = self._create_annotator()
        self.pull_document_url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})


    def test_all(self):
        self.run_entity_annotator_group()
        self.run_entity_annotation()


    def _create_annotator(self):
        payload = {
            "description": "Random test annotation.",
            "indices": [{"name": self.test_index_name}, {"name": self.secondary_index}],
            "query": json.dumps(TEST_QUERY),
            "fields": [TEST_FIELD],
            "annotating_users": ["annotator"],
            "annotation_type": "entity",
            "entity_configuration": {
                "fact_name": "TOXICITY"
            }
        }
        response = self.client.post(self.list_view_url, data=payload, format="json")
        print_output("_create_annotator:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        total_count = self.ec.es.count(index=f"{self.test_index_name},{self.secondary_index}").get("count", 0)
        self.assertTrue(total_count > response.data["total"])
        return response.data


    def _pull_random_document(self):
        url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        response = self.client.post(url, format="json")
        return response.data

    def run_entity_annotator_group(self):
        annotator_children = []
        for i in range(2):
            child = self._create_annotator()
            annotator_children.append(child["id"])
        group_url = reverse("v2:annotator_groups-list", kwargs={"project_pk": self.project.pk})
        group_payload = {
            "parent": self.annotator["id"],
            "children": annotator_children
        }
        group_response = self.client.post(group_url, data=group_payload, format="json")
        print_output("run_entity_annotator_group:response.status", group_response.status_code)
        self.assertTrue(group_response.status_code == status.HTTP_201_CREATED)


    def run_entity_annotation(self):
        annotation_url = reverse("v2:annotator-annotate-entity", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        print_output("run_entity_annotation:annotation_url", annotation_url)
        annotation_payloads = []
        for i in range(2):
            random_document = self._pull_random_document()
            annotation_payloads.append(
                {"index": random_document["_index"], "document_id": random_document["_id"], "texta_facts": [{"doc_path": TEST_FIELD, "fact": "TOXICITY", "spans": "[[0,0]]", "str_val": "bar", "source": "annotator"}]}
            )
        print_output("annotation_document_before_0", annotation_payloads[0]['document_id'])
        print_output("annotation_document_before_1", annotation_payloads[1]['document_id'])
        while annotation_payloads[0]['document_id'] == annotation_payloads[1]['document_id']:
            random_document = self._pull_random_document()
            annotation_payloads[1] = {"index": random_document["_index"], "document_id": random_document["_id"], "texta_facts": [{"doc_path": TEST_FIELD, "fact": "TOXICITY", "spans": "[[0,0]]", "str_val": "bar", "source": "annotator"}]}
        print_output("run_entity_annotation:annotation_payloads", annotation_payloads)
        for index_count, payload in enumerate(annotation_payloads):
            print_output(f"run_entity_annotation:annotation_payload{index_count}", payload['document_id'])
            annotation_response = self.client.post(annotation_url, data=payload, format="json")
            # Test for response success.
            print_output("run_entity_annotation:response.status", annotation_response.status_code)
            self.assertTrue(annotation_response.status_code == status.HTTP_200_OK)

            # Test that progress is updated properly.
            model_object = Annotator.objects.get(pk=self.annotator["id"])
            print_output("run_entity_annotation:annotator_model_obj", model_object.annotated)
            print_output("run_entity_annotation:entity_index_count", index_count)
            self.assertTrue(model_object.annotated == index_count + 1)

            # Check that document was actually edited.
            es_doc = self.ec.es.get(index=payload["index"], id=payload["document_id"])["_source"]
            facts = es_doc["texta_facts"]
            print_output("facts", facts)
            print_output("mode_object", model_object.entity_configuration.fact_name)
            self.assertTrue(model_object.entity_configuration.fact_name in [fact["fact"] for fact in facts])


@override_settings(CELERY_ALWAYS_EAGER=True)
class MultilabelAnnotatorTests(APITestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.index, is_created = Index.objects.get_or_create(name=self.test_index_name)
        self.user = create_test_user('annotator', 'my@email.com', 'pw')
        self.project = project_creation("multilabelTestProject", self.test_index_name, self.user)
        self.project.indices.add(self.index)
        self.project.users.add(self.user)

        self.client.login(username='annotator', password='pw')
        self.ec = ElasticCore()

        self.list_view_url = reverse("v2:annotator-list", kwargs={"project_pk": self.project.pk})
        self.labelset_url = reverse("v2:labelset-list", kwargs={"project_pk": self.project.pk})
        self.get_facts_url = reverse("v2:get_facts", kwargs={"project_pk": self.project.pk})
        self.facts = self._get_facts()
        self.labelset = self._create_labelset()
        self.annotator = self._create_annotator()
        self.pull_document_url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})

    def test_all(self):
        self.run_multilabel_annotation()
        self.run_empty_multilabel_annotation()

    def _create_annotator(self):
        payload = {
            "description": "Random test annotation.",
            "indices": [{"name": self.test_index_name}],
            "query": json.dumps(TEST_QUERY),
            "fields": [TEST_FIELD],
            "annotating_users": ["annotator"],
            "annotation_type": "multilabel",
            "multilabel_configuration": {
                "labelset": self.labelset["id"]
            }
        }
        response = self.client.post(self.list_view_url, data=payload, format="json")
        print_output("_create_annotator:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        return response.data

    def _get_facts(self):
        payload = {}
        response = self.client.post(self.get_facts_url, data=payload, format="json")
        print_output("_get_facts:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        return response.data

    def _create_labelset(self):
        payload = {
            "category": "new",
            "value_limit": 500,
            "indices": [self.test_index_name],
            "fact_names": [self.facts[0]["name"]],
            "values": ["true"]
        }
        response = self.client.post(self.labelset_url, data=payload, format="json")
        print_output("_create_labelset:response.status", response.status_code)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        return response.data

    def _pull_random_document(self):
        url = reverse("v2:annotator-pull-document", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        response = self.client.post(url, format="json")
        return response.data

    def run_multilabel_annotation(self):
        annotation_url = reverse("v2:annotator-annotate-multilabel", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        print_output("run_multilabel_annotation:annotation_url", annotation_url)
        random_document = self._pull_random_document()

        # Get model object before annotation.
        model_object_before = Annotator.objects.get(pk=self.annotator["id"])
        annotations_before = model_object_before.annotated
        print_output("run_multilabel_annotation:annotations_before", annotations_before)

        annotation_payload = {
            "document_id": random_document["_id"],
            "index": random_document["_index"],
            "labels": self.labelset["values"]
        }

        print_output(f"run_multilabel_annotation:annotation_payload", annotation_payload['document_id'])
        annotation_response = self.client.post(annotation_url, data=annotation_payload, format="json")
        # Test for response success.
        print_output("run_multilabel_annotation:response.status", annotation_response.status_code)
        self.assertTrue(annotation_response.status_code == status.HTTP_200_OK)

        # Test that progress is updated properly.
        model_object_after = Annotator.objects.get(pk=self.annotator["id"])
        annotations_after = model_object_after.annotated
        print_output("run_multilabel_annotation:annotations_after", annotations_after)
        self.assertTrue(annotations_after == annotations_before + 1)

    def run_empty_multilabel_annotation(self):
        annotation_url = reverse("v2:annotator-annotate-multilabel", kwargs={"project_pk": self.project.pk, "pk": self.annotator["id"]})
        print_output("run_multilabel_annotation:annotation_url", annotation_url)
        random_document = self._pull_random_document()

        # Get model object before annotation.
        model_object_before = Annotator.objects.get(pk=self.annotator["id"])
        annotations_before = model_object_before.annotated
        print_output("run_empty_multilabel_annotation:annotations_before", annotations_before)

        annotation_payload = {
            "document_id": random_document["_id"],
            "index": random_document["_index"],
            "labels": []
        }

        print_output(f"run_empty_multilabel_annotation:annotation_payload", annotation_payload['document_id'])
        annotation_response = self.client.post(annotation_url, data=annotation_payload, format="json")
        # Test for response success.
        print_output("run_empty_multilabel_annotation:response.status", annotation_response.status_code)
        self.assertTrue(annotation_response.status_code == status.HTTP_200_OK)

        # Test that progress is updated properly.
        model_object_after = Annotator.objects.get(pk=self.annotator["id"])
        annotations_after = model_object_after.annotated
        print_output("run_empty_multilabel_annotation:annotations_after", annotations_after)
        self.assertTrue(annotations_after == annotations_before + 1)
