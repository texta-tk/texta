import csv
import json
import pickle
import numpy as np
import matplotlib.pyplot as plt
import os
from typing import List, Dict

from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.helper_functions import create_file_path
from texta.settings import USER_MODELS, MODELS_DIR, ERROR_LOGGER, URL_PREFIX, MEDIA_URL, PROTECTED_MEDIA
import logging

# Task imports
from ..base_worker import BaseWorker
from task_manager.tools import ShowSteps
from task_manager.tools import TaskCanceledException
from task_manager.tools import get_pipeline_builder
from task_manager.tools import EsDataSample
from task_manager.models import Task

# Data imports
from sklearn.model_selection import train_test_split
from keras.preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer, text_to_word_sequence

# Keras Model imports
from keras.optimizers import Adam
from keras.activations import relu, elu, softmax, sigmoid
from keras.utils import plot_model

# Talos imports
import talos as ta
from talos import Deploy
from talos.model.layers import hidden_layers
from talos.model.normalizers import lr_normalizer
from talos.utils.best_model import activate_model, best_model

# Import clr callback and model architectures
from task_manager.tasks.workers.neuroclassifier.neuro_models import NeuroModels
from task_manager.tasks.workers.neuroclassifier.clr_callback import CyclicLR

np.random.seed(1337)

class NeuroClassifierWorker(BaseWorker):
    def __init__(self):

        """
        Main class for training the NeuroClassifier
        
        Arguments:
            samples {List[str]} -- List of str for the training data
            labels {List[str]} -- List of int for the labels
            model_arch {str} -- The model architecture
            validation_split {float} -- The percentage of data to use for validation
            crop_amount {int} -- If given, the amount to crop the training data. Useful for quick prototyping.
            grid_downsample_amount {float} -- The amount to downsample the grid search of the hyperparameters. Recommended less than 0.01 to avoid computation cost and time.
            max_seq_len {int} -- The maximum sequence length given by the user. Used for deriving self.final_seq_len
            num_epochs {int} -- In case of non-auto model, num_epochs will be the number of epochs to train the model for
        """

        # Task params
        self.task_id = None
        self.task_obj = None
        self.task_type = None
        self.task_params = None
        self.show_progress = None
        self.model_name = None

        # Neuroclassifier params
        self.model_arch = None
        self.validation_split = None
        self.crop_amount = None
        self.grid_downsample_amount = None
        self.max_seq_len = None
        self.num_epochs = None
        self.bs = 64

        # Neuroclassifier data
        self.samples = None
        self.labels = None

        # Derived params
        self.vocab_size = None
        self.final_seq_len = None

        # Processed data
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.tokenizer = None
        self.model = None


    def _set_up_task(self, task_id):
        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.task_type = self.task_obj.task_type
        self.task_params = json.loads(self.task_obj.parameters)
        self.model_name = 'model_{0}'.format(self.task_obj.unique_id)

        self.model_arch = self.task_params['model_arch']
        self.max_seq_len = int(self.task_params['max_seq_len'])
        self.num_epochs = int(self.task_params['num_epochs'])
        self.crop_amount = int(self.task_params['crop_amount'])
        self.validation_split = float(self.task_params['validation_split'])
        self.grid_downsample_amount = float(self.task_params['grid_downsample_amount'])

        steps = ["preparing data", "processing data", "training", "saving", "done"]
        self.show_progress = ShowSteps(self.task_id, steps)
        self.show_progress.update_view()


    def _build_data_sampler(self):
        self.show_progress.update(0)
        # Check if query was explicitly set
        if 'search_tag' in self.task_params:
            # Use set query
            param_query = self.task_params['search_tag']
        else:
            # Otherwise, load query from saved search
            param_query = self._parse_query(self.task_params)

        negative_set_multiplier = float(self.task_params['negative_multiplier_opt'])
        max_sample_size_opt = int(self.task_params['max_sample_size_opt']) if self.task_params['max_sample_size_opt'] != 'false' else False
        score_threshold_opt = float(self.task_params['score_threshold_opt'])
        fields = self.task_params['fields']

        # Build Data sampler
        ds = Datasets().activate_datasets_by_id(self.task_params['dataset'])
        es_m = ds.build_manager(ES_Manager)
        es_data = EsDataSample(fields=fields, 
                                query=param_query,
                                es_m=es_m,
                                negative_set_multiplier=negative_set_multiplier,
                                max_positive_sample_size=max_sample_size_opt,
                                score_threshold=score_threshold_opt)
        data_sample_x, data_sample_y, statistics = es_data.get_data_samples(with_fields=False)
        self.samples = data_sample_x
        self.labels = data_sample_y


    def _train_model(self):
        self.show_progress.update(2)
        if self.model_is_auto:
            self._train_auto_model()
        else:
            history = self._train_generic_model()
        return history


    def run(self, task_id):
        self._set_up_task(task_id)
        self._validate_params()

        self._build_data_sampler()
        self._process_data()
        self._get_model()
        training_history = self._train_model()
        loss_plot_url, acc_plot_url, model_plot_url = self._plot_model_and_history(training_history)
        val_eval, train_eval = self._cross_validation()
        self._create_task_result(val_eval, train_eval, loss_plot_url, acc_plot_url, model_plot_url)
        self._save_model()

        self.show_progress.update(4)
        self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        # TODO validate params
        # TODO average/percentile seq len
        # TODO preprocessor
        # TODO verbose overview
        # TODO validate that auto models work
        # TODO import speed overview
        # TODO pretrained embedding
        # validation result into results #DONE
        # final seq/vocab size into results #DONE
        # num_epocs param #DONE
        # model summary to front #DONE
        # debug why val results are random
        # fix max sample size per class 
        # conda install graphviz
        # conda install keras/cuda/etc


    def _create_task_result(self, val_eval, train_eval, loss_plot_url, acc_plot_url, model_plot_url):
        train_summary = {
            'X_train.shape': self.X_train.shape,
            'y_train.shape': self.y_train.shape,
            'X_val.shape': self.X_val.shape,
            'y_val.shape': self.y_val.shape,
            'final_seq_len': self.final_seq_len,
            'vocab_size': self.vocab_size,
            'val_acc': "{0:.4f}".format(val_eval[1]),
            'val_loss': "{0:.4f}".format(val_eval[0]),
            'train_acc': "{0:.4f}".format(train_eval[1]),
            'train_loss': "{0:.4f}".format(train_eval[0]),
            'tokenizer_num_words': len(self.tokenizer.word_index),
            # NOTE Save plots as HTML images for now, whilst there is no better alternative
            'acc_plot':  '<img src="{}" style="max-width: 80%">'.format(acc_plot_url),
            'loss_plot':  '<img src="{}" style="max-width: 80%">'.format(loss_plot_url),
            'model_plot':  '<img src="{}" style="max-width: 80%">'.format(model_plot_url),
        }
        self.task_obj.result = json.dumps(train_summary)


    def _cross_validation(self):
        # Evaluate model, get [loss, accuracy]
        val_eval = self.model.evaluate(x=self.X_val, y=self.y_val, batch_size=self.bs, verbose=1)
        train_eval = self.model.evaluate(x=self.X_train, y=self.y_train, batch_size=self.bs, verbose=1)
        return val_eval, train_eval


    def _save_model(self):
        try:
            self.show_progress.update(3)
            # create_file_path from helper_functions creates missing folders and returns a path
            output_model_file = create_file_path(self.model_name, MODELS_DIR, self.task_type)
            output_tokenizer_file = create_file_path('{}_{}'.format(self.model_name, 'tokenizer'), MODELS_DIR, self.task_type)
            self.model.save(output_model_file)
            with open(output_tokenizer_file, 'wb') as handle:
                pickle.dump(self.tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error('Failed to save NeuroClassifier model to the filesystem.', exc_info=True, extra={
                'model_name': self.model_name,
                'file_path':  output_model_file
            })


    def _get_model(self):
        model_obj = NeuroModels().get_model(self.model_arch)
        self.model_is_auto = model_obj['auto']
        self.model = model_obj['model']


    def _process_data(self):
        self.show_progress.update(1)
        # Declare Keras Tokenizer
        self.tokenizer = Tokenizer(
                    num_words=self.vocab_size, # If self.vocab_size is not None, limit vocab size
                    filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n\'')

        # Build Tokenizer on training vocab
        self.tokenizer.fit_on_texts(self.samples)
        # Tokenize sequences from words to integers
        self.X_train = self.tokenizer.texts_to_sequences(self.samples)

        # Get the max length of sequence of X_train values
        uncropped_max_len = max((len(x) for x in self.X_train))
        # Set the final seq_len to be either the max_seq_len or the max unpadded/cropped in present in the dataset
        # TODO in the future, use values such as "average length" or "top X-th percentile length" for more optimal seq_len
        self.final_seq_len = min(self.max_seq_len, uncropped_max_len)

        # Pad sequence to match MAX_SEQ_LEN
        self.X_train = pad_sequences(self.X_train, maxlen=self.final_seq_len)

        # Split data, so it would be shuffeled before cropping
        self.X_train, self.X_val, self.y_train, self.y_val = train_test_split(self.X_train, self.labels, test_size=self.validation_split, random_state=42)
        # Crop the training data if crop_amount is given
        if self.crop_amount:
            self.X_train = self.X_train[:self.crop_amount]
            self.y_train = np.array(self.y_train[:self.crop_amount])
            self.X_val = self.X_val[:self.crop_amount]
            self.y_val = np.array(self.y_val[:self.crop_amount])

        # Change self.vocab_size to the final vocab size, if it was less than the max
        final_vocab_size = len(self.tokenizer.word_index)
        if not self.vocab_size or final_vocab_size < self.vocab_size:
            self.vocab_size = final_vocab_size


    def _train_generic_model(self):
        # Custom cyclical learning rate callback
        clr_triangular = CyclicLR(mode='triangular', step_size=6*(len(self.X_train)/self.bs))
        self.model = self.model(self.vocab_size, self.final_seq_len)
        history = self.model.fit(self.X_train, self.y_train,
                        batch_size=self.bs,
                        epochs=self.num_epochs,
                        verbose=2,
                        # validation_split=self.validation_split,
                        validation_data=(self.X_val, self.y_val),
                        callbacks=[clr_triangular]
                        )
        return history


    def _train_auto_model(self):
        # Param space for Talos model to search through
        # Tuples values are a range, Lists are choice options
        p = {
            'lr': (0.5, 5, 10),
            'first_neuron': [24, 48, 96],
            'e_size':[128, 300],
            'h_size':[32, 64],
            'hidden_layers':[2,3],
            'activation':[relu],
            'batch_size': [64],
            'epochs': [2, 5],
            'dropout': (0, 0.20, 10),
            'optimizer': [Adam],
            'seq_len': [self.final_seq_len],
            'vocab_size': [self.vocab_size],
            'last_activation': [sigmoid]
        }

        # Talos scan that will find the best model with the parameters above
        h = ta.Scan(self.X_train, self.y_train,
            params=p,
            model=self.model,
            grid_downsample=self.grid_downsample_amount,
            val_split=0, # Zerofy val_split in Talos, because we pass in our own val data
            x_val=self.X_val,
            y_val=self.y_val
        )

        # Get only the model from the Talos experiment
        best_model_index = best_model(h, 'val_acc', False)
        self.model = activate_model(h, best_model_index)

        # For summary
        # model_summary = self.model.summary()
        # For model json object
        # model_json = self.model.to_json()
        # print(model_summary)
        # print(model_json)
        # For svg of model
        # from keras.utils import plot_model
        # plot_model(self.model, to_file='model.png') # TODO proper file path
        # Also TODO https://keras.io/visualization/


    def _validate_params(self):
        # TODO validate params
        # If proper, set them
        pass

    
    def _plot_model_and_history(self, history):
        # Plot training & validation accuracy values
        plt.plot(history.history['acc'])
        plt.plot(history.history['val_acc'])
        plt.title('Model accuracy')
        plt.ylabel('Accuracy')
        plt.xlabel('Epoch')
        plt.legend(['Train', 'Test'], loc='upper left')
        acc_plot_name = "{}_acc.svg".format(self.model_name)
        acc_plot_path = create_file_path(acc_plot_name, PROTECTED_MEDIA, "task_manager/", self.task_type)
        acc_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager/", self.task_type, acc_plot_name)
        plt.savefig(acc_plot_path, format="svg", bbox_inches='tight')
        plt.clf()

        # Plot training & validation loss values
        plt.plot(history.history['loss'])
        plt.plot(history.history['val_loss'])
        plt.title('Model loss')
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.legend(['Train', 'Test'], loc='upper left')
        loss_plot_name = "{}_loss.svg".format(self.model_name)
        loss_plot_path = create_file_path(loss_plot_name, PROTECTED_MEDIA, "task_manager/", self.task_type)
        loss_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager/", self.task_type, loss_plot_name)
        plt.savefig(loss_plot_path, format="svg", bbox_inches='tight')
        plt.clf()

        # Plot Keras model
        model_plot_name = "{}_model.svg".format(self.model_name)
        model_plot_path = create_file_path(model_plot_name, PROTECTED_MEDIA, "task_manager/", self.task_type)
        model_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager/", self.task_type, model_plot_name)
        plot_model(self.model, to_file=model_plot_path, show_shapes=True)

        return loss_plot_url, acc_plot_url, model_plot_url
