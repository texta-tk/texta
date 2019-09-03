from keras import backend as K
from keras.models import Sequential
from keras.layers import (Dense,
                          Embedding,
                          CuDNNLSTM,
                          CuDNNGRU, GRU,
                          Bidirectional,
                          Dropout,
                          MaxPooling1D,
                          Conv1D,
                          GlobalAveragePooling1D,
                          MaxPooling1D,
                          Flatten,
                         )
from keras.activations import relu, elu, softmax, sigmoid
from keras.optimizers import Adam, Nadam
from keras.losses import categorical_crossentropy, logcosh
from keras.utils import multi_gpu_model


class NeuroModels():
    FNN = "fnn"
    CNN = "cnn"
    GRU = "gru"
    LSTM = "lstm"
    GRUCNN = "gruCNN"
    LSTMCNN = "lstmCNN"

    def __init__(self):
        # Map models to string so they would be easy to call
        self.models_map = {
            NeuroModels.FNN: self.fnn,
            NeuroModels.CNN: self.cnn,
            NeuroModels.GRU: self.gru,
            NeuroModels.LSTM: self.lstm,
            NeuroModels.GRUCNN: self.gruCNN,
            NeuroModels.LSTMCNN: self.lstmCNN,
        }


    def get_model(self, model_arch, vocab_sz, seq_len, num_cls):

        if model_arch in self.models_map:
            model = self.models_map[model_arch](vocab_sz, num_cls, seq_len)
            model = self._compile_model(model)
            return model
        else:
            raise ValueError('"{}" is not a valid model architecture!'.format(model_arch))

    # Simplier models
    @staticmethod
    def fnn(vocab_sz, num_cls, seq_len):
        embed_dim = 300
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(Flatten())
        model.add(Dropout(0.5))
        model.add(Dense(32, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    @staticmethod
    def cnn(vocab_sz, num_cls, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(GlobalAveragePooling1D())
        model.add(Dense(20, activation='relu'))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    @staticmethod
    def gru(vocab_sz, num_cls, seq_len):
        embed_dim = 200
        n_hidden = 32
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(CuDNNGRU(n_hidden,))
        model.add(Dropout(0.5))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    @staticmethod
    def lstm(vocab_sz, num_cls, seq_len):
        embed_dim = 200
        n_hidden = 32
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(CuDNNLSTM(n_hidden))
        model.add(Dropout(0.5))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    # Combined models
    @staticmethod
    def gruCNN(vocab_sz, num_cls, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(CuDNNGRU(32))
        model.add(Dropout(0.5))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    @staticmethod
    def lstmCNN(vocab_sz, num_cls, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_sz, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(CuDNNLSTM(32))
        model.add(Dropout(0.5))
        model.add(Dense(num_cls, activation='sigmoid'))

        return model


    @staticmethod
    def _compile_model(model, loss='binary_crossentropy', optimizer='adam', metrics=['accuracy']):
        # Activate multi_gpu_model if more than 1 gpu found
        gpus = K.tensorflow_backend._get_available_gpus()
        if len(gpus) > 1:
            model = multi_gpu_model(model)

        model.compile(loss=loss,
                    optimizer=optimizer,
                    metrics=metrics)

        return model