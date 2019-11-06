from toolkit.elastic.document import ElasticDocument
from toolkit.tools.logger import Logger

import json


class Feedback:

    def __init__(self, project_pk, model_pk, model_type="tagger"):
        self.project_pk = project_pk
        self.model_pk = model_pk
        self.model_type = model_type
        self.es_doc = self._initialize_es_doc(project_pk)

    def _initialize_es_doc(self, project_pk):
        feedback_index = f"texta-feedback-project-{project_pk}"
        return ElasticDocument(feedback_index)

    def store(self, predicted_content, prediction):
        """
        Stores document with initial prediction in ES.
        """
        feedback_doc = {
            "predicted_content": predicted_content,
            "original_prediction": json.dumps(prediction)
        }
        try:
            # add document and return id
            return self.es_doc.add(feedback_doc)["_id"]
        except Exception as e:
            Logger().error("Failed indexing model feedback", exc_info=e)
            return None

    def add_feedback(self, feedback_id, correct_prediction):
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
        pass

    def get_content(self):
        """
        Retrieves content for a given model.
        """
        pass
