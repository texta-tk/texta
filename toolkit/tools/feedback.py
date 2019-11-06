from toolkit.elastic.document import ElasticDocument
from toolkit.tools.logger import Logger


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
        feedback_doc = {
            "predicted_content": predicted_content,
            "prediction": prediction
        }

        try:
            # add document and return id
            return self.es_doc.add(feedback_doc)["_id"]
        except Exception as e:
            Logger().error(f'Failed indexing tagger feedback', exc_info=e)
            return None


    def add_feedback(self, feedback_id, correct_prediction):
        pass
