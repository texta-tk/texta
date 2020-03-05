from sklearn.metrics import confusion_matrix, precision_score, recall_score, roc_curve, auc,f1_score, accuracy_score
import json

class TorchTaggingReport:

    def __init__(self, y_test, y_pred, average="macro"):
        self.f1_score = f1_score(y_test, y_pred, average=average)
        self.confusion = confusion_matrix(y_test, y_pred)
        self.precision = precision_score(y_test, y_pred, average=average)
        self.recall = recall_score(y_test, y_pred, average=average)
        self.accuracy = accuracy_score(y_test, y_pred)
        self.training_loss = None

        
    def to_dict(self):
        return {
            "f1_score": round(self.f1_score, 5),
            "precision": round(self.precision, 5),
            "recall": round(self.recall, 5),
            "confusion_matrix": self.confusion.tolist(),
            "accuracy": round(self.accuracy, 5),
            "training_loss": round(self.training_loss.astype(float), 5)
        }
