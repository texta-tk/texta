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
from keras.models import load_model
from keras.optimizers import Adam
from keras.activations import relu, elu, softmax, sigmoid
from keras.utils import plot_model

# Talos imports
import talos as ta
from talos import Deploy
from talos.model.layers import hidden_layers
from talos.model.normalizers import lr_normalizer
from talos.utils.best_model import activate_model, best_model
from talos.commands.reporting import Reporting

# Import clr callback and model architectures
from task_manager.tasks.workers.neuroclassifier.neuro_models import NeuroModels
from task_manager.tasks.workers.neuroclassifier.clr_callback import CyclicLR


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
            seq_len {int} -- The sequence length for the model, can be limited by the given as max_seq_len param
            vocab_size {int} -- The vocabulary size for the model, can be limited by the user as a max_vocab_size param
            num_epochs {int} -- In case of non-auto model, num_epochs will be the number of epochs to train the model for
        """

        # Task params
        self.task_id = None
        self.task_obj = None
        self.task_type = None
        self.task_params = None
        self.show_progress = None
        self.model_name = None
        self.task_result = {}

        # Neuroclassifier params
        self.model_arch = None
        self.validation_split = None
        self.crop_amount = None
        self.grid_downsample_amount = None
        self.num_epochs = None
        self.bs = 64

        # Neuroclassifier data
        self.samples = None
        self.labels = None

        # Derived params
        self.vocab_size = None
        self.seq_len = None

        # Processed data
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.tokenizer = None
        self.model = None


    def run(self, task_id):
        self._set_up_task(task_id)

        self._build_data_sampler()
        self._process_data()
        self._get_model()
        self._train_model()
        self._cross_validation()
        self._create_task_result()
        self._save_model()

        self.show_progress.update(4)
        self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        # TODO preprocessor

        # conda install graphviz
        # conda install keras/cuda/etc
        # pip install git+https://github.com/autonomio/talos.git@daily-dev --upgrade


    def _set_up_task(self, task_id):
        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.task_type = self.task_obj.task_type
        self.task_params = json.loads(self.task_obj.parameters)
        self.model_name = 'model_{0}'.format(self.task_obj.unique_id)

        self.model_arch = self.task_params['model_arch']
        self.seq_len = int(self.task_params['max_seq_len'])
        self.vocab_size = int(self.task_params['max_vocab_size'])
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
        # Set the final seq_len to be either the user set seq_len or the max unpadded/cropped in present in the dataset
        # TODO in the future, use values such as "average length" or "top X-th percentile length" for more optimal seq_len
        self.seq_len = min(self.seq_len, uncropped_max_len)

        # Pad sequence to match max seq_len
        self.X_train = pad_sequences(self.X_train, maxlen=self.seq_len)

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


    def _train_model(self):
        self.show_progress.update(2)
        if self.model_is_auto:
            scan = self._train_auto_model()
            self._plot_auto_model(scan)
        else:
            history = self._train_generic_model()
            self._plot_generic_model(history)


    def _get_model(self):
        model_obj = NeuroModels().get_model(self.model_arch)
        self.model_is_auto = model_obj['auto']
        self.model = model_obj['model']


    def _train_generic_model(self):
        # Custom cyclical learning rate callback
        clr_triangular = CyclicLR(mode='triangular', step_size=6*(len(self.X_train)/self.bs))
        self.model = self.model(self.vocab_size, self.seq_len)
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
            'seq_len': [self.seq_len],
            'vocab_size': [self.vocab_size],
            'last_activation': [sigmoid],
            'shapes': ['brick', 'triangle', 'funnel']
        }
        scan_filename = "{}_scan".format(self.model_name)
        scan_filepath = create_file_path(scan_filename, PROTECTED_MEDIA, "task_manager", self.task_type)

        # Talos scan that will find the best model with the parameters above
        scan = ta.Scan(self.X_train, self.y_train,
            params=p,
            model=self.model,
            grid_downsample=self.grid_downsample_amount,
            val_split=0, # Zerofy val_split in Talos, because we pass in our own val data
            x_val=self.X_val,
            y_val=self.y_val,
            experiment_name=scan_filepath
        )

        # Get only the model from the Talos experiment
        best_model_index = best_model(scan, 'val_acc', False)
        self.model = activate_model(scan, best_model_index)
        self.model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])

        return scan

    def _create_task_result(self):
        train_summary = {
            'X_train.shape': self.X_train.shape,
            'y_train.shape': self.y_train.shape,
            'X_val.shape': self.X_val.shape,
            'y_val.shape': self.y_val.shape,
            'seq_len': self.seq_len,
            'vocab_size': self.vocab_size,
            'model_json': self.model.to_json(),
        }

        self.task_result.update(train_summary)
        self.task_obj.result = json.dumps(self.task_result)


    def _cross_validation(self):
        # Evaluate model, get [loss, accuracy]
        val_eval = self.model.evaluate(x=self.X_val, y=self.y_val, batch_size=self.bs, verbose=1)
        train_eval = self.model.evaluate(x=self.X_train, y=self.y_train, batch_size=self.bs, verbose=1)

        self.task_result['val_acc'] = "{0:.4f}".format(val_eval[1]),
        self.task_result['val_loss'] = "{0:.4f}".format(val_eval[0]),
        self.task_result['train_acc'] = "{0:.4f}".format(train_eval[1]),
        self.task_result['train_loss'] = "{0:.4f}".format(train_eval[0]),


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


    def _plot_auto_model(self, scan):
        # Set results
        report = Reporting(scan)
        self.task_result['Number of rounds in the experiment'] = int(report.rounds())
        self.task_result['Number of rounds it took to get highest result'] = int(report.rounds2high())
        self.task_result['Highest train_acc'] = "{0:.4f}".format(report.high('acc'))
        self.task_result['Highest val_acc'] = "{0:.4f}".format(report.high())
        self.task_result['Highest train_loss'] = "{0:.4f}".format(report.high('loss'))
        self.task_result['Highest val_loss'] = "{0:.4f}".format(report.high('val_loss'))
        self.task_result['Lowest train_acc'] = "{0:.4f}".format(report.low('acc'))
        self.task_result['Lowest val_acc'] = "{0:.4f}".format(report.low())
        self.task_result['Lowest train_loss'] = "{0:.4f}".format(report.low('loss'))
        self.task_result['Lowest val_loss'] = "{0:.4f}".format(report.low('val_loss'))


        # Plot
        scan_plot_name = "{}_auto_acc.svg".format(self.model_name)
        scan_plot_path = create_file_path(scan_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        scan_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, scan_plot_name)
        report.plot_line()
        plt.savefig(scan_plot_path, format="svg", bbox_inches='tight')
        self.task_result['Auto model val_acc per round'] = '<img src="{}" style="max-width: 80%">'.format(scan_plot_url)


    def _plot_generic_model(self, history):
        # Plot training & validation accuracy values
        plt.plot(history.history['acc'])
        plt.plot(history.history['val_acc'])
        plt.title('Model accuracy')
        plt.ylabel('Accuracy')
        plt.xlabel('Epoch')
        plt.legend(['Train', 'Test'], loc='upper left')
        acc_plot_name = "{}_acc.svg".format(self.model_name)
        acc_plot_path = create_file_path(acc_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        acc_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, acc_plot_name)
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
        loss_plot_path = create_file_path(loss_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        loss_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, loss_plot_name)
        plt.savefig(loss_plot_path, format="svg", bbox_inches='tight')
        plt.clf()

        # Plot Keras model
        model_plot_name = "{}_model.svg".format(self.model_name)
        model_plot_path = create_file_path(model_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        model_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, model_plot_name)
        plot_model(self.model, to_file=model_plot_path, show_shapes=True)

        # NOTE Save plots as HTML images for now, whilst there is no better alternative
        self.task_result['acc_plot'] = '<img src="{}" style="max-width: 80%">'.format(acc_plot_url)
        self.task_result['loss_plot'] = '<img src="{}" style="max-width: 80%">'.format(loss_plot_url)
        self.task_result['model_plot'] = '<img src="{}" style="max-width: 80%">'.format(model_plot_url)


    def load(self, task_id):
        '''Load model/tokenizer for preprocessor'''
        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.model_name = 'model_{}'.format(self.task_obj.unique_id)
        self.task_type = self.task_obj.task_type
        model_path = os.path.join(MODELS_DIR, self.task_type, self.model_name)

        tokenizer_name = '{}_tokenizer'.format(self.model_name)
        tokenizer_path = os.path.join(MODELS_DIR, self.task_type, tokenizer_name)

        try:
            self.model = load_model(model_path)
            self.tokenizer = pickle.load(tokenizer_path)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error('Failed to load model from the filesystem.', exc_info=True, extra={
                'model_name': self.model_name,
                'file_path':  model_path,
                'tokenizer_name': tokenizer_name,
                'tokenizer_path': tokenizer_path,
            })
