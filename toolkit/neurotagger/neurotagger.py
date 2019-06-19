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
from texta.settings import USER_MODELS, MODELS_DIR, URL_PREFIX, MEDIA_URL, PROTECTED_MEDIA
from texta.settings import ERROR_LOGGER, INFO_LOGGER

# Task imports
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
from keras import backend as K
from keras.callbacks import Callback
from keras.models import load_model
from keras.optimizers import Adam
from keras.activations import relu, elu, softmax, sigmoid
from keras.utils import plot_model

# Import model architectures
from toolkit.neurotagger.neuro_models import NeuroModels


class NeuroClassifierWorker():
    def __init__(self):
        """
        Main class for training the NeuroClassifier

        # conda install graphviz
        # conda install keras/cuda/etc
        Arguments:
            samples {List[str]} -- List of str for the training data
            labels {List[str]} -- List of int for the labels
            model_arch {str} -- The model architecture
            validation_split {float} -- The percentage of data to use for validation
            grid_downsample_amount {float} -- The amount to downsample the grid search of the hyperparameters. Recommended less than 0.01 to avoid computation cost and time.
            seq_len {int} -- The sequence length for the model, can be limited by the given as max_seq_len param
            vocab_size {int} -- The vocabulary size for the model, can be limited by the user as a max_vocab_size param
            num_epochs {int} -- The number of epochs to train the model for
        """

        # Task params
        self.task_id = None
        self.task_obj = None
        self.task_type = None
        self.task_params = None
        self.model_name = None
        self.show_steps = None
        self.task_result = {}

        # Neuroclassifier params
        self.model_arch = None
        self.validation_split = None
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
        try:
            self._set_up_task(task_id)

            self._build_data_sampler()
            self._process_data()
            self._get_model()
            self._train_model()
            self._cross_validation()
            self._create_task_result()
            self._save_model()

            self.show_steps.update(4)
            self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

        except Exception as e:
            self.task_obj.result = json.dumps({'error': repr(e)})
            self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=True)


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
        self.validation_split = float(self.task_params['validation_split'])
        self.grid_downsample_amount = float(self.task_params['grid_downsample_amount'])

        steps = ["preparing data", "processing data", "training", "saving", "done"]
        self.show_steps = ShowSteps(self.task_id, steps)
        self.show_steps.update_view()


    def _build_data_sampler(self):
        self.show_steps.update(0)
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
        self.show_steps.update(1)
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

        # Convert labels to numpy arrays
        self.y_train = np.array(self.y_train)
        self.y_val = np.array(self.y_val)

        # Change self.vocab_size to the final vocab size, if it was less than the max
        final_vocab_size = len(self.tokenizer.word_index)
        if not self.vocab_size or final_vocab_size < self.vocab_size:
            # Add 1 to vocab to avoid OOV error because of the last value
            self.vocab_size = final_vocab_size + 1


    def _train_model(self):
        self.show_steps.update(2)
        history = self._train_generic_model()
        self._plot_generic_model(history)


    def _get_model(self):
        model_obj = NeuroModels().get_model(self.model_arch)
        self.model = model_obj['model']

    
    def _train_generic_model(self):
        # Create a new ShowSteps updater for training
        epoch_steps = ['Training: Epoch' for i in range(self.num_epochs)]
        show_epochs = ShowSteps(self.task_id, epoch_steps)
        show_epochs.update_view()
        # Training callback which shows progress to the user
        trainingProgress = TrainingProgressCallback(show_epochs=show_epochs)
        # Custom cyclical learning rate callback
        self.model = self.model(self.vocab_size, self.seq_len)
        history = self.model.fit(self.X_train, self.y_train,
                        batch_size=self.bs,
                        epochs=self.num_epochs,
                        verbose=2,
                        # validation_split=self.validation_split,
                        validation_data=(self.X_val, self.y_val),
                        callbacks=[trainingProgress]
                        )
        return history


    def _create_task_result(self):
        train_summary = {
            'X_train.shape': self.X_train.shape,
            'y_train.shape': self.y_train.shape,
            'X_val.shape': self.X_val.shape,
            'y_val.shape': self.y_val.shape,
            'max_sequence_len': self.seq_len,
            'vocabulary_size': self.vocab_size,
            'model_json': self.model.to_json(),
        }

        self.task_result.update(train_summary)
        self.task_obj.result = json.dumps(self.task_result)


    def _cross_validation(self):
        # Evaluate model, get [loss, accuracy]
        val_eval = self.model.evaluate(x=self.X_val, y=self.y_val, batch_size=self.bs, verbose=1)
        train_eval = self.model.evaluate(x=self.X_train, y=self.y_train, batch_size=self.bs, verbose=1)
        self.task_result['Validation accuracy'] = "{0:.4f}".format(val_eval[1])
        self.task_result['Validation loss'] = "{0:.4f}".format(val_eval[0])
        self.task_result['Training accuracy'] = "{0:.4f}".format(train_eval[1])
        self.task_result['Training loss'] = "{0:.4f}".format(train_eval[0])


    def _save_model(self):
        self.show_steps.update(3)
        # create_file_path from helper_functions creates missing folders and returns a path
        output_model_file = create_file_path(self.model_name, MODELS_DIR, self.task_type)
        output_tokenizer_file = create_file_path('{}_{}'.format(self.model_name, 'tokenizer'), MODELS_DIR, self.task_type)
        self.model.save(output_model_file)
        with open(output_tokenizer_file, 'wb') as handle:
            pickle.dump(self.tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)


    def _plot_generic_model(self, history):
        fig, ax = plt.subplots(1, 2, figsize=(16,8))
        # Plot training & validation accuracy values
        ax[0].plot(history.history['acc'])
        ax[0].plot(history.history['val_acc'])
        ax[0].set_title('Model accuracy')
        ax[0].set_ylabel('Accuracy')
        ax[0].set_xlabel('Epoch')
        ax[0].legend(['Train', 'Test'], loc='upper left')

        # Plot training & validation loss values
        ax[1].plot(history.history['loss'])
        ax[1].plot(history.history['val_loss'])
        ax[1].set_title('Model loss')
        ax[1].set_ylabel('Loss')
        ax[1].set_xlabel('Epoch')
        ax[1].legend(['Train', 'Test'], loc='upper left')
        acc_loss_plot_name = "{}_acc_loss.svg".format(self.model_name)
        acc_loss_plot_path = create_file_path(acc_loss_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        acc_loss_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, acc_loss_plot_name)
        plt.savefig(acc_loss_plot_path, format="svg", bbox_inches='tight')
        plt.clf()

        # Plot Keras model
        model_plot_name = "{}_model.svg".format(self.model_name)
        model_plot_path = create_file_path(model_plot_name, PROTECTED_MEDIA, "task_manager", self.task_type)
        model_plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager", self.task_type, model_plot_name)
        plot_model(self.model, to_file=model_plot_path, show_shapes=True)

        # NOTE Save plots as HTML images for now, whilst there is no better alternative
        self.task_result['acc_loss_plot'] = '<img src="{}" style="max-width: 800px">'.format(acc_loss_plot_url)
        self.task_result['model_plot'] = '<img src="{}" style="max-width: 400px">'.format(model_plot_url)


    def load(self, task_id):
        '''Load model/tokenizer for preprocessor'''
        K.clear_session()
        # Clear Keras session, because currently this function
        # is called in every elastic scroll batch, because
        # preprocessor worker just calls the .transform() function
        # on Task preprocessors, reloading the models on every bad (bad).
        # This also causes a memory leak in Tensorflow, to prevent it,
        # clear the session, or rework the entire preprocessor system

        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.model_name = 'model_{}'.format(self.task_obj.unique_id)
        self.task_type = self.task_obj.task_type
        model_path = os.path.join(MODELS_DIR, self.task_type, self.model_name)
        self.seq_len = json.loads(self.task_obj.result)['max_sequence_len']
        tokenizer_name = '{}_tokenizer'.format(self.model_name)
        tokenizer_path = os.path.join(MODELS_DIR, self.task_type, tokenizer_name)

        self.model = load_model(model_path)
        with open(tokenizer_path, 'rb') as f:
            self.tokenizer = pickle.load(f)


    def convert_and_predict(self, text):
        to_predict = self.tokenizer.texts_to_sequences(text)
        to_predict = pad_sequences(to_predict, maxlen=self.seq_len)
        return self.model.predict_classes(to_predict, batch_size=self.bs)


class TrainingProgressCallback(Callback):
    """Callback for updating the Task Progress every epoch
    
    Arguments:
        show_epochs {ShowSteps} -- ShowSteps callback to be called in on_epoch_end
    """
    def __init__(self, show_epochs):
        self.show_epochs = show_epochs

    def on_epoch_end(self, epoch, logs={}):
        # Use on_epoch_end because on_epoch_begin logs are empty
        eval_info = '[acc {:.2f}%, loss {:.2f}] [val_acc {:.2f}%, val_loss {:.2f}]'.format(
                                                                logs['acc'] * 100,
                                                                logs['loss'],
                                                                logs['val_acc'] * 100,
                                                                logs['val_loss'])

        self.show_epochs.update(epoch, extra_string=eval_info)
