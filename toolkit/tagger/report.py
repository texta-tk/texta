from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix, precision_score, recall_score

class TaggingReport:

    def __init__(self, y_test, y_pred):
        self.f1_score = f1_score(y_test, y_pred, average='micro')
        self.confusion = confusion_matrix(y_test, y_pred)
        self.precision = precision_score(y_test, y_pred)
        self.recall = recall_score(y_test, y_pred)
        self.accuracy = None
        self.training_loss = None
