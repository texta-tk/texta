from itertools import product
import matplotlib
# For non-GUI rendering
matplotlib.use('agg')
import matplotlib.pyplot as plt
from toolkit.tools.plot_utils import save_plot
import numpy as np

def create_torchtagger_plot(statistics):
    """
    This function is for plotting tagger statistics.
    """
    plt.figure(figsize=(4, 4))

    # TODO: Figure out how to retrieve class names for confusion matrix    
    classes = [range(0, len(statistics.confusion[0]))]

    cm = statistics.confusion
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

    return save_plot(plt)
