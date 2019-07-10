import os
import csv
import json
import pickle
import secrets
import numpy as np
from io import BytesIO
from typing import List, Dict

# For non-GUI rendering
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt


from django.core.files.base import ContentFile
from toolkit.settings import MODELS_DIR, MEDIA_URL
from toolkit.neurotagger.models import Neurotagger
from toolkit.utils.plot_utils import save_plot
# Data management imports
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
from keras.utils.vis_utils import model_to_dot

# Import model architectures
from toolkit.neurotagger.neuro_models import NeuroModels




class NeurotaggerWorker():
    def __init__(self, neurotagger_id):
        """
        Main class for training the NeuroClassifier

        # conda install graphviz
        # conda install keras/cuda/etc
        Arguments:
            samples {List[str]} -- List of str for the training data
            labels {List[str]} -- List of int for the labels
            model_arch {str} -- The model architecture
            validation_split {float} -- The percentage of data to use for validation
            seq_len {int} -- The sequence length for the model, can be limited by the given as max_seq_len param
            vocab_size {int} -- The vocabulary size for the model, can be limited by the user as a max_vocab_size param
            num_epochs {int} -- The number of epochs to train the model for
            show_progress {ShowProgress} -- ShowProgress for info callbacks
            neurotagger_obj {Neurotagger} -- The associated Neurotagger object, where to save results, etc
        """

        # Task params
        self.neurotagger_id = neurotagger_id
        self.neurotagger_obj = None
        self.task_type = None
        self.model_name = None
        self.show_progress = None
        self.task_result = {}

        # Neuroclassifier params
        self.model_arch = None
        self.validation_split = None
        self.num_epochs = None
        self.bs = 64

        # Derived params
        self.num_classes = None
        self.vocab_size = None
        self.seq_len = None

        # Neuroclassifier data
        self.samples = None
        self.labels = None

        # Processed data
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.tokenizer = None
        self.model = None


    def _set_up_data(self, samples, labels, show_progress):
        self.neurotagger_obj = Neurotagger.objects.get(pk=self.neurotagger_id)
        self.show_progress = show_progress

        self.model_arch = self.neurotagger_obj.model_architecture
        self.validation_split = self.neurotagger_obj.validation_split
        self.num_epochs = self.neurotagger_obj.num_epochs

        # Derived params
        self.vocab_size = self.neurotagger_obj.vocab_size
        self.seq_len = self.neurotagger_obj.seq_len

        # Data
        self.samples = samples
        self.labels = labels
        self.show_progress = show_progress


    def run(self, samples, labels, show_progress):
        self._set_up_data(samples, labels, show_progress)
        self._process_data()
        self.model = NeuroModels().get_model(self.model_arch)
        import pdb; pdb.set_trace()
        history = self._train_model()
        self._plot_model(history)
        self._cross_validation()

        self._create_task_result()
        self._save_model()


    def _process_data(self):
        self.show_progress.update_step(1)
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
        # Update the seq_len of the obj
        self.neurotagger_obj.seq_len = self.seq_len
        self.neurotagger_obj.save()

        # Pad sequence to match max seq_len
        self.X_train = pad_sequences(self.X_train, maxlen=self.seq_len)

        # Split data, so it would be shuffeled before cropping
        self.X_train, self.X_val, self.y_train, self.y_val = train_test_split(self.X_train, self.labels, test_size=self.validation_split, random_state=42)

        # Convert labels to numpy arrays, use np.expand_dims to include the last dimension shape
        # Eg shape == (800,) becomes shape == (800, 1); shape == (num_of_training_examples, num_classes)
        import pdb; pdb.set_trace()
        self.y_train = np.expand_dims(np.array(self.y_train), 1)
        self.y_val = np.expand_dims(np.array(self.y_val), 1)

        # Set up num_classes for the neural net last layer output size. Get the last shape size of y.
        self.num_classes = self.y_train.shape[-1]

        # Change self.vocab_size to the final vocab size, if it was less than the max
        final_vocab_size = len(self.tokenizer.word_index)
        if not self.vocab_size or final_vocab_size < self.vocab_size:
            # Add 1 to vocab to avoid OOV error because of the last value
            self.vocab_size = final_vocab_size + 1


    
    def _train_model(self):
        # Training callback which shows progress to the user
        trainingProgress = TrainingProgressCallback(show_progress=self.show_progress)

        self.model = self.model(self.vocab_size, self.seq_len, self.num_classes)
        return self.model.fit(self.X_train, self.y_train,
                        batch_size=self.bs,
                        epochs=self.num_epochs,
                        verbose=2,
                        # validation_split=self.validation_split,
                        validation_data=(self.X_val, self.y_val),
                        callbacks=[trainingProgress]
                    )


    def _create_task_result(self):
        train_summary = {
            'X_train.shape': self.X_train.shape,
            'y_train.shape': self.y_train.shape,
            'X_val.shape': self.X_val.shape,
            'y_val.shape': self.y_val.shape,
            'model_json': self.model.to_json(),
            'num_classes': self.num_classes,
        }

        self.task_result.update(train_summary)
        self.neurotagger_obj.result_json = json.dumps(self.task_result)


    def _cross_validation(self):
        # Evaluate model, get [loss, accuracy]
        val_eval = self.model.evaluate(x=self.X_val, y=self.y_val, batch_size=self.bs, verbose=1)
        train_eval = self.model.evaluate(x=self.X_train, y=self.y_train, batch_size=self.bs, verbose=1)
        self.neurotagger_obj.validation_accuracy = val_eval[1]
        self.neurotagger_obj.training_accuracy =  train_eval[1]
        self.neurotagger_obj.validation_loss = val_eval[0]
        self.neurotagger_obj.training_loss = train_eval[0]


    def _save_model(self):
        self.show_progress.update_step(3)
        # create_file_path from helper_functions creates missing folders and returns a path
        model_path = f'neurotagger_{self.neurotagger_obj.id}_{secrets.token_hex(10)}'
        output_model_file = os.path.join(MODELS_DIR, 'neurotagger', model_path)
        self.model.save(output_model_file)

        output_tokenizer_file = os.path.join(MODELS_DIR,
            'neurotagger', f'neurotagger_tokenizer_{self.neurotagger_obj.id}_{secrets.token_hex(10)}'
        )
        with open(output_tokenizer_file, 'wb') as handle:
            pickle.dump(self.tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)
        
        self.neurotagger_obj.location = json.dumps({'model': output_model_file, 'tokenizer': output_tokenizer_file})
        self.neurotagger_obj.save()


    def _plot_model(self, history):
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
        acc_loss_plot_path = f'{secrets.token_hex(15)}.png'
        self.neurotagger_obj.plot.save(acc_loss_plot_path, save_plot(plt))
        plt.clf()

        # Plot Keras model
        model_plot_path = f'{secrets.token_hex(15)}.png'
        # Get byte representation of the plot
        model_plot = model_to_dot(self.model).create(prog='dot', format='png')
        # Wrap it as a Django ContentFile, and save to model
        c_f = ContentFile(model_plot)
        self.neurotagger_obj.model_plot.save(model_plot_path, c_f)


    def load(self):
        '''Load model/tokenizer for preprocessor'''
        K.clear_session()
        # Clear Keras session, because currently this function
        # is called in every elastic scroll batch, because
        # preprocessor worker just calls the .transform() function
        # on Task preprocessors, reloading the models on every bad (bad).
        # This also causes a memory leak in Tensorflow, to prevent it,
        # clear the session, or rework the entire preprocessor system

        self.neurotagger_obj = Neurotagger.objects.get(pk=self.neurotagger_id)
        self.seq_len = self.neurotagger_obj.seq_len
        self.model = load_model(json.loads(self.neurotagger_obj.location)['model'])
        with open(json.loads(self.neurotagger_obj.location)['tokenizer'], 'rb') as f:
            self.tokenizer = pickle.load(f)

    def _convert_texts(self, texts: List[str]):
        texts = self.tokenizer.texts_to_sequences(texts)
        texts = pad_sequences(texts, maxlen=self.seq_len)
        return texts


    def tag_text(self, text):
        """
        Predicts on raw text
        :param text: input text as string
        :return: class names of decision
        """
        to_predict = self._convert_texts([text])
        return self.model.predict_classes(to_predict, batch_size=self.bs), self.model.predict_proba(to_predict, batch_size=self.bs)


    def tag_doc(self, doc):
        """
        Predicts on json document
        :param text: input doc as json string
        :return: binary decision (1 is positive)
        """
        texts = [doc[field] for field in doc]
        to_predict = self._convert_texts(texts)
        return self.model.predict_classes(to_predict, batch_size=self.bs), self.model.predict_proba(to_predict, batch_size=self.bs)

    
    def _convert_labels_to_multiple_hot(labels, num_classes):
        pass


class TrainingProgressCallback(Callback):
    """Callback for updating the Task Progress every epoch
    
    Arguments:
        show_epochs {ShowSteps} -- ShowSteps callback to be called in on_epoch_end
    """
    def __init__(self, show_progress):
        self.show_progress = show_progress

    def on_epoch_end(self, epoch, logs={}):
        # Use on_epoch_end because on_epoch_begin logs are empty
        eval_info = 'epoch - {}; [acc {:.2f}%, loss {:.2f}] [val_acc {:.2f}%, val_loss {:.2f}]'.format(
                                                                epoch,
                                                                logs['acc'] * 100,
                                                                logs['loss'],
                                                                logs['val_acc'] * 100,
                                                                logs['val_loss'])

        self.show_progress.update_step(f'Training: {eval_info}')
