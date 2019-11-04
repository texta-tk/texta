
from itertools import product
import matplotlib
# For non-GUI rendering
matplotlib.use('agg')
import matplotlib.pyplot as plt
from toolkit.tools.plot_utils import save_plot
import numpy as np


def create_tagger_plot(statistics):
    """
    This function is for plotting tagger statistics.
    """
    plt.figure(figsize=(12, 4))

    # calculate & plot roc curve
    plt.subplot(1, 3, 1)
    lw = 2
    plt.plot(statistics['false_positive_rate'], statistics['true_positive_rate'], color='darkorange',
                lw=lw, label='ROC curve (area = %0.2f)' % statistics['area_under_curve'])
    plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver operating characteristic')
    plt.legend(loc="lower right")

    # plot confusion matrix
    plt.subplot(1, 3, 2)
    classes = ['negative', 'positive']
    cm = statistics['confusion_matrix']
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion matrix')
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)
    fmt = 'd'
    thresh = cm.max() / 2.
    for i, j in product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                horizontalalignment="center",
                color="white" if cm[i, j] > thresh else "black")
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()

    # calculate & plot feature coefficients
    feature_coefs = sorted(statistics['feature_coefs'])
    plt.subplot(1, 3, 3)
    plt.plot(feature_coefs)
    plt.ylabel('Coefficient')
    plt.xlabel('Features')
    plt.title('Feature coefficient distribution')

    return save_plot(plt)
