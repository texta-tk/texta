from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.query import Query
from toolkit.tools.logger import Logger

import json


class Feedback:

    def __init__(self, project_pk, model_pk=None, model_type="tagger", text_processor=None, callback_progress=None, prediction_to_match=None):
        self.es_core = ElasticCore()
        self.project_pk = project_pk
        self.feedback_index = f"texta-feedback-project-{project_pk}"
        self.model_pk = model_pk
        self.model_type = model_type
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
        # create mathing query
        query = Query()
        query.add_string_filter(query_string=self.model_type, fields=["model_type"])
        if self.model_pk:
            query.add_string_filter(query_string=str(self.model_pk), fields=["model_id"])
        if prediction_to_match:
            query.add_string_filter(query_string=prediction_to_match, fields=["correct_prediction"])
        # if no index, don't create searcher object
        if not self.check_index_exists():
            return es_doc, None, query.query
        # create es search
        es_search = ElasticSearcher(
                indices=self.feedback_index,
                query = query.query,
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
        return self.es_search.search()['hits']['hits']

    def store(self, predicted_content, prediction):
        """
        Stores document with initial prediction in ES.
        """
        feedback_doc = {
            "model_id": str(self.model_pk),
            "model_type": self.model_type,
            "predicted_content": json.dumps(predicted_content),
            "original_prediction": json.dumps(prediction)
        }

        try:
            # add document and return id
            return self.es_doc.add(feedback_doc)["_id"]
        except Exception as e:
            Logger().error("Failed indexing model feedback", exc_info=e)
            return None

    def add(self, feedback_id, correct_prediction):
        """
        Adds correct prediction to indexed doc.
        """
        try:
            document = self.es_doc.get(feedback_id)
            document["correct_prediction"] = json.dumps(correct_prediction)
            self.es_doc.update(feedback_id, document)
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
            return {"success": f"deleted {deleted} feedback items."}
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
