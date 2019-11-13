import torch
from torch import nn
import torch.optim as optim
from torchtext import data
from torchtext.vocab import Vectors
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score

from .torch_models.text_cnn.model import TextCNN
from .torch_models.text_cnn.config import Config

#from .torch_models.fasttext.model import fastText
#from .torch_models.fasttext.config import Config

class TorchTagger:

    def __init__(self, embedding):
        self.config = Config()
        self.embedding = embedding

    @staticmethod
    def evaluate_model(model, iterator):
        all_preds = []
        all_y = []
        for idx,batch in enumerate(iterator):
            if torch.cuda.is_available():
                x = batch.text.cuda()
            else:
                x = batch.text
            y_pred = model(x)
            predicted = torch.max(y_pred.cpu().data, 1)[1]
            all_preds.extend(predicted.numpy())
            all_y.extend(batch.label.numpy())
        score = accuracy_score(all_y, np.array(all_preds).flatten())
        return score

    def train(self, data_sample):
        # TODO: replace with normal tokenizer
        # my first hacky tokenizer
        tokenizer = lambda sent: [x.strip() for x in sent.split(" ")]

        # Creating Field for data
        text_field = data.Field(sequential=True, tokenize=tokenizer, lower=True)
        label_field = data.Field(sequential=False, use_vocab=False)
        datafields = [("text", text_field), ("label", label_field)]

        positives = list(data_sample.positives)
        negatives = list(data_sample.negatives)

        # combine samples and create labels
        texts = positives+negatives
        labels = [1]*len(positives)+[0]*len(negatives)

        # retrieve vectors and vocab dict from embedding
        embedding_matrix, word2index = self.embedding.tensorize()

        # set embedding size according to the dimensionality embedding model
        embedding_size = len(embedding_matrix[0])
        self.config.embed_size = embedding_size

        # create pandas dataframe and torchtext dataset
        train_dataframe = pd.DataFrame({"texts": texts, "labels": labels})
        train_examples = [data.Example.fromlist(i, datafields) for i in train_dataframe.values.tolist()]
        train_data = data.Dataset(train_examples, datafields)

        # split data for training and testing
        train_data, test_data = train_data.split(split_ratio=self.config.split_ratio)
        # split training data again for validation during training
        train_data, val_data = train_data.split(split_ratio=self.config.split_ratio)

        # build vocab (without vectors)
        text_field.build_vocab(train_data)
        # add word vectors to vocab
        text_field.vocab.set_vectors(word2index, embedding_matrix, embedding_size)

        # Create Model with specified optimizer and loss function
        ##############################################################
        model = TextCNN(self.config, len(text_field.vocab), text_field.vocab.vectors, self.evaluate_model)
        
        if torch.cuda.is_available():
            model.cuda()
        model.train()
        optimizer = optim.SGD(model.parameters(), lr=self.config.lr)
        NLLLoss = nn.NLLLoss()
        model.add_optimizer(optimizer)
        model.add_loss_op(NLLLoss)
        ##############################################################

        train_iterator = data.BucketIterator(
            (train_data),
            batch_size = self.config.batch_size,
            sort_key = lambda x: len(x.text),
            repeat = False,
            shuffle = True
        )
        
        val_iterator, test_iterator = data.BucketIterator.splits(
            (val_data, test_data),
            batch_size=self.config.batch_size,
            sort_key=lambda x: len(x.text),
            repeat=False,
            shuffle=False)


        train_losses = []
        val_accuracies = []
        
        for i in range(self.config.max_epochs):
            print ("Epoch: {}".format(i))
            train_loss, val_accuracy = model.run_epoch(train_iterator, val_iterator, i)
            train_losses.append(train_loss)
            val_accuracies.append(val_accuracy)
