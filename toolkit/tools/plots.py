from itertools import product
from io import BytesIO
from django.core.files.base import ContentFile
import matplotlib

# For non-GUI rendering
matplotlib.use('agg')
import matplotlib.pyplot as plt
import numpy as np


def save_plot(plt):
    f = BytesIO()
    plt.savefig(f)
    return ContentFile(f.getvalue())


def create_tagger_plot(statistics: dict):
    """
    This function is for plotting tagger statistics.
    Only plot ROC curve for binary problems.
    """
    # retrieve class names
    classes = statistics['classes']
    # set plot size based on number of classes
    if len(classes) == 2:
        plt.figure(figsize=(8, 4))
    else:
        plt.figure(figsize=(4, 4))
    # calculate & plot roc curve
    if len(classes) == 2:
        plt.subplot(1, 2, 1)
        lw = 2
        plt.plot(statistics['false_positive_rate'], statistics['true_positive_rate'], color='darkorange',
                lw=lw, label='ROC curve (area = %0.2f)' % statistics['area_under_curve'])
        plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver operating characteristic')
        plt.legend(loc="lower right")
    # plot confusion matrix
    # set values based on number of classes
    if len(classes) == 2:
        plt.subplot(1, 2, 2)
    else:
        plt.subplot(1, 1, 1)
    cm = np.asarray(statistics['confusion_matrix'])
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion matrix')
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)
    fmt = 'd'
    thresh = cm.max() / 1.5
    for i, j in product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    # save & return
    return save_plot(plt)
