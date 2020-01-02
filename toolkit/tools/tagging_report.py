from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix, precision_score, recall_score
import json

class TaggingReport:

    def __init__(self, y_test, y_pred):
        self.f1_score = f1_score(y_test, y_pred, average='macro')
        self.confusion = confusion_matrix(y_test, y_pred)
        self.precision = precision_score(y_test, y_pred, average='macro')
        self.recall = recall_score(y_test, y_pred, average='macro')
        self.accuracy = None
        self.training_loss = None

    def to_dict(self):
        return {
            'f1_score': str(round(self.f1_score, 3)),
            'precision': str(round(self.precision, 3)),
            'recall': str(round(self.recall, 3)),
            'accuracy': str(round(self.accuracy, 3)),
            'training_loss': str(round(self.training_loss, 3))
        }