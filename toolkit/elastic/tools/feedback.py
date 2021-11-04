from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_elastic.core import ElasticCore
from texta_elastic.query import Query
from toolkit.tools.logger import Logger
from toolkit.helper_functions import get_core_setting
from django.conf import settings

from datetime import datetime
import json


class Feedback:

    def __init__(self, project_pk, model_object=None, text_processor=None, callback_progress=None,
                 prediction_to_match=None, es_prefix=get_core_setting("TEXTA_ES_PREFIX"),
                 deploy_key=getattr(settings, "DEPLOY_KEY")):
        self.es_core = ElasticCore()
        self.project_pk = project_pk
        self.feedback_index = f"{es_prefix}texta-{deploy_key}-feedback-project-{project_pk}"
        self.model_object = model_object
        self.es_doc, self.es_search, self.query = self._initialize_es(project_pk, text_processor, callback_progress, prediction_to_match)


    def __iter__(self):
        """
        Iterator for iterating through scroll of documents for given model
        """
        if self.check_index_exists():
            return self.es_search.scroll()
        else:
            return iter(())


    def check_index_exists(self):
        return self.es_core.check_if_indices_exist([self.feedback_index])


    def _initialize_es(self, project_pk, text_processor, callback_progress, prediction_to_match):
        # create es doc
        es_doc = ElasticDocument(self.feedback_index)
        # if no model objects, return nones for query and search
        if not self.model_object:
            return es_doc, None, None
        # create mathing query
        query = Query()
        query.add_string_filter(query_string=self.model_object.MODEL_TYPE, fields=["model_type"])
        if self.model_object:
            query.add_string_filter(query_string=str(self.model_object.pk), fields=["model_id"])
        if prediction_to_match:
            query.add_string_filter(query_string=prediction_to_match, fields=["correct_result"])
        # if no index, don't create searcher object
        if not self.check_index_exists():
            return es_doc, None, query.query
        # create es search
        es_search = ElasticSearcher(
            indices=self.feedback_index,
            query=query.query,
            text_processor=text_processor,
            output=ElasticSearcher.OUT_DOC_WITH_ID,
            callback_progress=callback_progress
        )
        # return objects
        return es_doc, es_search, query.query


    def list(self):
        """
        Lists feedback for a given model.
        """
        # this is because the index might not exist yet
        # check the _initialize_es method for more info
        if not self.es_search:
            return []
        else:
            return self.es_search.search()['hits']['hits']


    def _text_to_doc(self, text):
        """
        Generates document dict using input text and list of fields.
        """
        # retrieve list of fields model was trained on
        model_fields = json.loads(self.model_object.fields)
        return {field_path: text for field_path in model_fields}


    def store(self, content, prediction):
        """
        Stores document with initial prediction in ES.
        """
        # if predicted on text, generate doc
        if isinstance(content, str):
            content = self._text_to_doc(content)
        # generate feedback doc wrapping predicted doc
        feedback_doc = {
            "model_id": str(self.model_object.pk),
            "model_type": self.model_object.MODEL_TYPE,
            "content": json.dumps(content),
            "original_prediction": str(prediction),
            "prediction_time": datetime.now()
        }

        try:
            # add document and return id
            return self.es_doc.add(feedback_doc)["_id"]
        except Exception as e:
            Logger().error("Failed indexing model feedback", exc_info=e)
            return None


    def add(self, feedback_id, correct_result):
        """
        Adds correct prediction to indexed doc.
        """
        try:
            document = self.es_doc.get(feedback_id)
            document["_source"]["correct_result"] = json.dumps(correct_result)
            document["_source"]["feedback_time"] = datetime.now()
            doc_type = document.get("_type", "_doc")
            self.es_doc.update(index=document["_index"], doc_id=feedback_id, doc=document["_source"], doc_type=doc_type)
            return {"success": "Tagger feedback updated."}

        except Exception as e:
            error_msg = "Failed changing model feedback."
            Logger().error(error_msg, exc_info=e)
            return {"error": f"{error_msg}: e"}


    def delete(self):
        """
        Deletes feedback for given model.
        """
        try:
            deleted = self.es_doc.delete_by_query(self.query)["deleted"]
            return {"success": f"deleted {deleted} feedback item(s)."}
        except Exception as e:
            error_msg = "Feedback document delete failed."
            Logger().error(error_msg, exc_info=e)
            return {"error": f"{error_msg}: e"}


    def delete_index(self):
        """
        Deletes feedback index for given project.
        """
        try:
            deleted = self.es_doc.core.delete_index(self.feedback_index)
            return {"success": f"deleted feedback index: {self.feedback_index}."}
        except Exception as e:
            error_msg = "Feedback index delete failed."
            Logger().error(error_msg, exc_info=e)
            return {"error": f"{error_msg}: e"}
