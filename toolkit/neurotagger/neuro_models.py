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


class NeuroModels():
    model_names = [
        'simpleFNN',
        'simpleCNN',
        'simpleGRU',
        'simpleLSTM',
        'gruCNN',
        'lstmCNN',
    ]

    def __init__(self):
        # Map models to string so they would be easy to call
        self.models_map = {
            'simpleFNN': self.simpleFNN,
            'simpleCNN': self.simpleCNN,
            'simpleGRU': self.simpleGRU,
            'simpleLSTM': self.simpleLSTM,
            'gruCNN': self.gruCNN,
            'lstmCNN': self.lstmCNN,
            'autoFNN': self.autoFNN,
            'autoGRU': self.autoGRU,
            'autoLSTM': self.autoLSTM,
            'autoCNN': self.autoCNN,
        }


    def get_model(self, model_arch):
        if model_arch in self.models_map:
            return self.models_map[model_arch]
        else:
            raise ValueError('"{}" is not a valid model architecture!'.format(model_arch))

    # Simplier models
    @staticmethod
    def simpleFNN(vocab_size, seq_len):
        embed_dim = 300
        print(vocab_size, seq_len)
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(Flatten())
        model.add(Dropout(0.5))
        model.add(Dense(32, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(1,activation='sigmoid'))
        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy'])
        return model


    @staticmethod
    def simpleCNN(vocab_size, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(GlobalAveragePooling1D())
        model.add(Dense(20, activation='relu'))
        model.add(Dense(1, activation='sigmoid'))

        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy'])
        return model


    @staticmethod
    def simpleGRU(vocab_size, seq_len):
        embed_dim = 200
        n_hidden = 32
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(CuDNNGRU(n_hidden,))
        model.add(Dropout(0.5))
        model.add(Dense(1,activation='sigmoid'))

        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics = ['accuracy'])
        return model


    @staticmethod
    def simpleLSTM(vocab_size, seq_len):
        embed_dim = 200
        n_hidden = 32
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(CuDNNLSTM(n_hidden))
        model.add(Dropout(0.5))
        model.add(Dense(1,activation='sigmoid'))

        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics = ['accuracy'])
        return model


    # Combined models
    @staticmethod
    def gruCNN(vocab_size, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(CuDNNGRU(32))
        model.add(Dropout(0.5))
        model.add(Dense(1, activation='sigmoid'))

        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy'])
        return model


    @staticmethod
    def lstmCNN(vocab_size, seq_len):
        embed_dim = 200
        model = Sequential()
        model.add(Embedding(vocab_size, embed_dim, input_length=seq_len))
        model.add(Conv1D(32, 7, activation='relu'))
        model.add(Dropout(0.5))
        model.add(CuDNNLSTM(32))
        model.add(Dropout(0.5))
        model.add(Dense(1, activation='sigmoid'))

        model.compile(loss='binary_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy'])

        return model
