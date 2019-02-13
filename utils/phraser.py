from gensim.models.phrases import Phrases
from gensim.models.phrases import Phraser as GSPhraser
from task_manager.models import Task
from texta.settings import MODELS_DIR
import os


class Phraser:

    def __init__(self, task_id):
        self.task_id = task_id
        self._phraser = None 
    
    def build(self, sentences):
        phrase_model = Phrases(sentences)
        phraser = GSPhraser(phrase_model)
        self._phraser = phraser

    def save(self, file_path):
        if self._phraser:
            self._phraser.save(file_path)
            return True
        return False

    def load(self):
        task_obj = Task.objects.get(pk=self.task_id)
        phraser_name = 'phraser_{}'.format(task_obj.unique_id)
        file_path = os.path.join(MODELS_DIR, task_obj.task_type, phraser_name)
        try:
            self._phraser = Phraser.load(file_path)
            return True
        except:
            return False

    def phrase(self, text):
        if self._phraser:
            return self._phraser[text]
        else:
            return text
