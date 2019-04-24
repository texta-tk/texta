import os
import glob
from itertools import product
import numpy as np
from django.core import serializers

import matplotlib
# For non-GUI rendering
matplotlib.use('agg')
import matplotlib.pyplot as plt


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


def create_file_path(filename, *args):
    '''
    Creates file path, eg for models/metadata/media.
    Params:
        filename - The name of the file
        args - Unpacked list of strings for directory of the file
    Example usage: 
        plot_url = self.create_file_path(plot_name, URL_PREFIX, MEDIA_URL, "task_manager", self.task_obj.task_type)
    '''

    dir_path = os.path.join(*args)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    full_path = os.path.join(dir_path, filename)

    return full_path

def write_task_xml(task_object, file_path):
    task_xml = serializers.serialize("xml", [task_object])
    with open(file_path, 'w') as fh:
        fh.write(task_xml)
    return True
