from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query
from toolkit.tools.logger import Logger

import json


class Feedback:

    def __init__(self, project_pk, model_pk=None, model_type="tagger"):
        self.project_pk = project_pk
        self.model_pk = model_pk
        self.model_type = model_type
        self.es_doc, self.es_search = self._initialize_es(project_pk)
        self.query = self._create_query()

    def _initialize_es(self, project_pk):
        feedback_index = f"texta-feedback-project-{project_pk}"
        return ElasticDocument(feedback_index), ElasticSearcher(indices=feedback_index)

    def _create_query(self):
        query = Query()
        query.add_string_filter(query_string=self.model_type, fields=["model_type"])
        if self.model_pk:
            query.add_string_filter(query_string=str(self.model_pk), fields=["model_id"])
        self.es_search.update_query = query.query
        return query.query     

    def store(self, predicted_content, prediction):
        """
        Stores document with initial prediction in ES.
        """
        feedback_doc = {
            "model_id": str(self.model_pk),
            "model_type": self.model_type,
            "predicted_content": predicted_content,
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
            deleted = self.es_doc.delete_by_query(self.es_search.query)["deleted"]
            return {"success": f"deleted {deleted} feedback items."}
        except:
            error_msg = "Feedback document delete failed."
            Logger().error(error_msg, exc_info=e)
            return {"error": f"{error_msg}: e"} 

    def delete_index(self):
        """
        Deletes feedback index for given project.
        """
        try:
            deleted = self.es_doc.core.delete_index(self.es_doc.index)
            return {"success": f"deleted feedback index: {self.es_doc.index}."}
        except:
            error_msg = "Feedback index delete failed."
            Logger().error(error_msg, exc_info=e)
            return {"error": f"{error_msg}: e"} 

    def list(self):
        """
        Lists feedback for a given model.
        """
        return self.es_search.search()
        
    def scroll(self):
        """
        Lists feedback for a given model.
        """
        self.es_search.scroll()
