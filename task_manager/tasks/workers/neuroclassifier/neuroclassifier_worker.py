import csv
import pickle
import numpy as np
from typing import List, Dict

# Data imports
from sklearn.model_selection import train_test_split
from keras.preprocessing.sequence import pad_sequences
from keras.preprocessing.text import Tokenizer, text_to_word_sequence

# Model imports
from keras.optimizers import Adam
from keras.activations import relu, elu, softmax, sigmoid

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

class NeuroClassifierWorker():
    def __init__(
            self,
            samples: List[str],
            labels: List[int],
            max_vocab_size: int,
            max_seq_len: int,
            model_arch: str,
            validation_split: float=0.2,
            crop_amount: int=None,
            grid_downsample_amount: float=0.001):

        """
        Main class for training the NeuroClassifier
        
        Arguments:
            samples {List[str]} -- List of str for the training data
            labels {List[str]} -- List of int for the labels
            model_arch {str} -- The model architecture
            validation_split {float} -- The percentage of data to use for validation
            crop_amount {int} -- If given, the amount to crop the training data. Useful for quick prototyping.
            grid_downsample_amount {float} -- The amount to downsample the grid search of the hyperparameters. Recommended less than 0.01 to avoid computation cost and time.
        """

        self.model_arch = model_arch
        self.validation_split = validation_split
        self.crop_amount = crop_amount
        self.grid_downsample_amount = grid_downsample_amount

        self.samples = samples
        self.labels = labels

        # Validated data
        self.vocab_size = max_vocab_size
        self.seq_len = max_seq_len

        # Processed data
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.tokenizer = None
        self.model = None


    def run(self):
        self._validate_params()
        self._process_data()
        print(self.vocab_size)
        self._get_model()
        # self._train_model()
        if self.model_is_auto:
            self._train_auto_model()
        else:
            self._train_model()

        self._save()


    def _save(self):
        self.model.save('MODELS/my_model.h5')

        # Save tokenizer for evaluation
        with open('MODELS/tokenizer.pkl', 'wb') as f:
            pickle.dump(self.tokenizer, f)


    def _get_model(self):
        model_obj = NeuroModels().get_model(self.model_arch)
        self.model_is_auto = model_obj['auto']
        self.model = model_obj['model']


    def _process_data(self):
        # Declare Keras Tokenizer
        self.tokenizer = Tokenizer(
                    num_words=self.vocab_size, # If self.vocab_size is not None, limit vocab size
                    filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n\'')

        # Build Tokenizer on training vocab
        self.tokenizer.fit_on_texts(self.samples)
        # Tokenize sequences from words to integers
        self.X_train = self.tokenizer.texts_to_sequences(self.samples)
        # Pad sequence to match MAX_SEQ_LEN
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
        if final_vocab_size < self.vocab_size:
            self.vocab_size = final_vocab_size


    def _train_model(self):
        bs = 64
        # Custom cyclical learning rate callback
        clr_triangular = CyclicLR(mode='triangular', step_size=6*(len(self.X_train)/bs))
        self.model = self.model(self.vocab_size, self.seq_len)
        self.model.fit(self.X_train, self.y_train,
                        batch_size=bs,
                        epochs=5,
                        verbose=2,
                        # validation_split=self.validation_split,
                        validation_data=(self.X_val, self.y_val),
                        callbacks=[clr_triangular]
                        )


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


if __name__ == '__main__':
    CROP = 5000
    def read_csv(path):
        samples = []
        with open(path, encoding='utf8') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                samples.append(row[0])
        return samples
    pos_samples = read_csv('C:/Users/ranet/Documents/DATA/Datasets/farm_not_farm_text_tagging/farmstuff.csv')[:CROP]
    neg_samples = read_csv('C:/Users/ranet/Documents/DATA/Datasets/farm_not_farm_text_tagging/notfarmstuff.csv')[:CROP]
    
    ## MAKE CLASSES
    # Combine both, add classes
    pos_y = [1 for x in range(len(pos_samples))]
    neg_y = [0 for x in range(len(neg_samples))]
    print(len(pos_y), len(neg_y))
    X = pos_samples + neg_samples
    y = pos_y + neg_y


    ### TEST HERE
    # neuro_classifier = NeuroClassifierWorker(['Hey this is the positive sample', 'and here is the negative one'], [1, 0], 100, 3, 'SimpleFNN')

    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'simpleFNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'autoFNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # TODO more dropout to certain models, the non auto ones
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'simpleCNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('SIMPLE CNN DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'simpleGRU', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('SIMPLE GRU DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'simpleLSTM', crop_amount=1000) # works
    # neuro_classifier.run()
    # # print('SIMPLE LSTM DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'gruCNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('GRU CNN DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'lstmCNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('LSTM CNN DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'autoCNN', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('AUTO CNN DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'autoGRU', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('AUTO GRU DONE')
    # neuro_classifier = NeuroClassifierWorker(X, y, 50000, 150, 'autoLSTM', crop_amount=1000) # works
    # neuro_classifier.run()
    # print('AUTO LSTM DONE')
    import pdb;pdb.set_trace()
