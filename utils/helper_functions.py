import matplotlib.pyplot as plt
import numpy as np
from itertools import product
import glob

def add_dicts(dict1, dict2):
    '''
    Helper function to += values of keys from two dicts with a single level nesting
    '''
    # Check if params are dict
    # Dicts are passed in as reference, so dict1 gets updated from call
    if set([type(dict1), type(dict2)]).issubset([dict]):
        for key, val in dict2.items():
            if key not in dict1:
                dict1[key] = val
            else:
                if type(val) == dict:
                    for k, v in val.items():
                        if type(v) != dict:
                            dict1[key][k] += v
                else:
                    dict1[key] += val

def plot_confusion_matrix(cm, classes, title='Confusion matrix'):
    """
    This function prints and plots the confusion matrix.
    """
    plt.figure()
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(title)
    tick_marks = np.arange(len(classes))
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
    return plt

def get_wildcard_files(path):
    '''
    Gets all the other files with a given name as prefix, uses wildcard.
    -   returns - [(str: path, str: filename)]
    '''
    files = []
    for file in glob.glob(path + '*'):
        # Add path and name
        files.append((file, os.path.basename(file)))

    return files