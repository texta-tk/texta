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

from talos.model.layers import hidden_layers
from talos.model.normalizers import lr_normalizer

class NeuroModels():
    model_names = [
        'simpleFNN',
        'simpleCNN',
        'simpleGRU',
        'simpleLSTM',
        'gruCNN',
        'lstmCNN',
        'autoFNN',
        'autoGRU',
        'autoLSTM',
        'autoCNN',
    ]

    def __init__(self):
        # Map models to string so they would be easy to call
        self.models_map = {
            'simpleFNN': { 'auto': False, 'model': self.simpleFNN },
            'simpleCNN': { 'auto': False, 'model': self.simpleCNN },
            'simpleGRU': { 'auto': False, 'model': self.simpleGRU },
            'simpleLSTM': { 'auto': False, 'model': self.simpleLSTM },
            'gruCNN': { 'auto': False, 'model': self.gruCNN },
            'lstmCNN': { 'auto': False, 'model': self.lstmCNN },
            'autoFNN': { 'auto': True, 'model': self.autoFNN },
            'autoGRU': { 'auto': True, 'model': self.autoGRU },
            'autoLSTM': { 'auto': True, 'model': self.autoLSTM },
            'autoCNN': { 'auto': True, 'model': self.autoCNN },
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

    # auto models
    @staticmethod
    def autoFNN(X_train, Y_train, X_val, Y_val, params):
        model = Sequential()
        model.add(Embedding(params['vocab_size'], params['e_size'], input_length=params['seq_len']))
        model.add(Flatten())
        hidden_layers(model, params, 1)
        model.add(Dense(1, activation=params['last_activation']))

        model.compile(optimizer=params['optimizer'](lr_normalizer(params['lr'], params['optimizer'])),
                    loss='binary_crossentropy',
                    metrics=['acc'])

        out = model.fit(X_train, Y_train,
                    batch_size=params['batch_size'],
                    epochs=params['epochs'],
                    validation_data=[X_val, Y_val],
                    verbose=2)

        return out, model


    @staticmethod
    def autoCNN(X_train, Y_train, X_val, Y_val, params):
        model = Sequential()
        model.add(Embedding(params['vocab_size'], params['e_size'], input_length=params['seq_len']))
        model.add(Conv1D(params['h_size'], 7, activation='relu'))
        model.add(Dropout(params['dropout']))
        model.add(GlobalAveragePooling1D())
        hidden_layers(model, params, 1)
        model.add(Dense(1, activation=params['last_activation']))

        ## COMPILE
        model.compile(optimizer=params['optimizer'](lr_normalizer(params['lr'], params['optimizer'])),
                    loss='binary_crossentropy',
                    metrics=['acc'])

        out = model.fit(X_train, Y_train,
                        batch_size=params['batch_size'],
                        epochs=params['epochs'],
                        validation_data=[X_val, Y_val],
                        verbose=2)

        return out, model


    @staticmethod
    def autoGRU(X_train, Y_train, X_val, Y_val, params):
        model = Sequential()
        model.add(Embedding(params['vocab_size'], params['e_size'], input_length=params['seq_len']))
        model.add(CuDNNGRU(params['h_size'],))
        hidden_layers(model, params, 1)
        model.add(Dense(1, activation=params['last_activation']))

        ## COMPILE
        model.compile(optimizer=params['optimizer'](lr_normalizer(params['lr'], params['optimizer'])),
                    loss='binary_crossentropy',
                    metrics=['acc'])

        out = model.fit(X_train, Y_train,
                        batch_size=params['batch_size'],
                        epochs=params['epochs'],
                        validation_data=[X_val, Y_val],
                        verbose=2)

        return out, model


    @staticmethod
    def autoLSTM(X_train, Y_train, X_val, Y_val, params):
        model = Sequential()
        model.add(Embedding(params['vocab_size'], params['e_size'], input_length=params['seq_len']))
        model.add(CuDNNLSTM(params['h_size'],))
        hidden_layers(model, params, 1)
        model.add(Dense(1, activation=params['last_activation']))

        ## COMPILE
        model.compile(optimizer=params['optimizer'](lr_normalizer(params['lr'], params['optimizer'])),
                    loss='binary_crossentropy',
                    metrics=['acc'])

        out = model.fit(X_train, Y_train,
                        batch_size=params['batch_size'],
                        epochs=params['epochs'],
                        validation_data=[X_val, Y_val],
                        verbose=2)

        return out, model
