import os
import csv
import json
import pickle
import secrets
import tempfile
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
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from keras.preprocessing.sequence import pad_sequences

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
import sentencepiece as spm


class NeurotaggerWorker():
    def __init__(self, neurotagger_id):
        """
        Main class for training the NeuroClassifier

        Arguments:
            samples {List[str]} -- List of str for the training data
            labels {List[int]} -- List of int for the labels
            label_names {List[str]} -- List of label names
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
        self.bs = 32

        # Derived params
        self.num_classes = None
        self.vocab_size = None
        self.seq_len = None

        # Neuroclassifier data
        self.samples = None
        self.labels = None
        self.label_names = None

        # Processed data
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.tokenizer = None
        self.model = None


    def _set_up_data(self, samples, labels, label_names, show_progress):
        self.neurotagger_obj = Neurotagger.objects.get(pk=self.neurotagger_id)
        self.show_progress = show_progress
        

        self.model_arch = self.neurotagger_obj.model_architecture
        self.validation_split = self.neurotagger_obj.validation_split
        self.num_epochs = self.neurotagger_obj.num_epochs

        # Derived params
        self.vocab_size = self.neurotagger_obj.vocab_size
        self.seq_len = self.neurotagger_obj.seq_len

        # Data
        self.label_names = label_names
        self.samples = samples
        self.labels = labels
        self.show_progress = show_progress


    def run(self, samples, labels, show_progress, label_names):
        self._set_up_data(samples, labels, label_names, show_progress)
        self._process_data()
        self.model = NeuroModels().get_model(self.model_arch)
        history = self._train_model()
        self._plot_model(history)
        self._cross_validation()

        self._create_task_result()
        self._save_model()
        # import pdb; pdb.set_trace()


    
    def _train_tokenizer(self):
        self.output_tokenizer_file = os.path.join(MODELS_DIR,
            'neurotagger', f'neurotagger_tokenizer_{self.neurotagger_obj.id}_{secrets.token_hex(10)}'
        )

        # As Sentencepiece requires a file as input, a tempfile will be created
        fd, temp_path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w', encoding="utf8") as tmp:
                # Dump the training samples to the file
                tmp.write(' \n\n '.join(self.samples))

                spm.SentencePieceTrainer.train(' '.join([
                    f'--input={temp_path}',
                    f'--max_sentence_length=20480',
                    f'--model_prefix={self.output_tokenizer_file}',
                    f'--vocab_size={self.vocab_size}',
                    f'--model_type=unigram'
                ]))
        finally:
            os.remove(temp_path)

    def _process_data(self):
        self.show_progress.update_step('Processing data')

        # Tokenize
        self._train_tokenizer()
        sp = spm.SentencePieceProcessor()
        sp.load(f'{self.output_tokenizer_file}.model')
        self.X_train = [sp.encode_as_ids(x) for x in self.samples]

        # Get the max length of sequence of X_train values
        uncropped_max_len = max((len(x) for x in self.X_train))
        # Set the final seq_len to be either the user set seq_len or the max unpadded/cropped in present in the dataset
        # Possible TODO in the future, use values such as "average length" or "top X-th percentile length" for more optimal seq_len
        self.seq_len = min(self.seq_len, uncropped_max_len)
        # Update the seq_len of the obj
        self.neurotagger_obj.seq_len = self.seq_len
        self.neurotagger_obj.save()

        # Pad sequence to match max seq_len
        self.X_train = pad_sequences(self.X_train, maxlen=self.seq_len)

        # Split data, so it would be shuffeled before cropping
        self.X_train, self.X_val, self.y_train, self.y_val = train_test_split(self.X_train, self.labels, test_size=self.validation_split, random_state=42)

        self.y_train = np.array(self.y_train)
        self.y_val = np.array(self.y_val)

        # Set up num_classes for the neural net last layer output size. Get the last shape size of y.
        self.num_classes = self.y_train.shape[-1]

    
    def _train_model(self):
        # Training callback which shows progress to the user
        trainingProgress = TrainingProgressCallback(self.num_epochs, self.show_progress)
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
        
        rounded_preds = np.round(self.model.predict(self.X_val))
        metrics = classification_report(self.y_val, rounded_preds, target_names=self.label_names)
        print(metrics)
        metrics = classification_report(self.y_val, rounded_preds, target_names=self.label_names, output_dict=True)
        self.neurotagger_obj.classification_report = json.dumps(metrics)


    def _save_model(self):
        self.show_progress.update_step('Saving model')
        # create_file_path from helper_functions creates missing folders and returns a path
        model_path = f'neurotagger_{self.neurotagger_obj.id}_{secrets.token_hex(10)}'
        output_model_file = os.path.join(MODELS_DIR, 'neurotagger', model_path)
        self.model.save(output_model_file)
        
        self.neurotagger_obj.location = json.dumps({
            'model': output_model_file,
            'tokenizer_model': f'{self.output_tokenizer_file}.model',
            'tokenizer_vocab': f'{self.output_tokenizer_file}.vocab'
        })

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

    def _convert_texts(self, texts: List[str]):
        sp = spm.SentencePieceProcessor()
        sp.load(json.loads(self.neurotagger_obj.location)['tokenizer_model'])
        texts = [sp.encode_as_ids(x) for x in texts]
        texts = pad_sequences(texts, maxlen=self.seq_len)
        
        
        return texts


    def tag_text(self, text):
        """
        Predicts on raw text
        :param text: input text as string
        :return: class names of decision
        """
        to_predict = self._convert_texts([text])
        return self.model.predict_proba(to_predict, batch_size=self.bs)


    def tag_doc(self, doc):
        """
        Predicts on json document
        :param text: input doc as json string
        :return: binary decision (1 is positive)
        """
        texts = [doc[field] for field in doc]
        to_predict = self._convert_texts(texts)
        return self.model.predict_proba(to_predict, batch_size=self.bs)
    

class TrainingProgressCallback(Callback):
    """Callback for updating the Task Progress every epoch
    
    Arguments:
        show_epochs {ShowSteps} -- ShowSteps callback to be called in on_epoch_end
    """
    def __init__(self, num_epochs, show_progress):
        self.show_progress = show_progress
        self.num_epochs = num_epochs

    def on_epoch_end(self, epoch, logs={}):
        # Use on_epoch_end because on_epoch_begin logs are empty
        eval_info = 'epoch - {}; [acc {:.2f}%, loss {:.2f}] [val_acc {:.2f}%, val_loss {:.2f}]'.format(
                                                                epoch,
                                                                logs['acc'] * 100,
                                                                logs['loss'],
                                                                logs['val_acc'] * 100,
                                                                logs['val_loss'])

        self.show_progress.update_step(f'Training: {eval_info}')
        self.show_progress.update_view(round(100 / (self.num_epochs + 1 / (epoch + 1)), 2))
