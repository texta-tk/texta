import torch
from torch import nn
import torch.optim as optim
from torchtext import data
from torchtext.vocab import Vectors
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score
from .torch_models.models import TORCH_MODELS
from toolkit.tagger.report import TaggingReport

class TorchTagger:

    def __init__(self, embedding, model_arch="fastText", n_classes=2, num_epochs=5):
        self.embedding = embedding
        self.config = TORCH_MODELS[model_arch]["config"]()
        self.model_arch = TORCH_MODELS[model_arch]["model"]
        # set number of output classes
        self.config.output_size = n_classes
        # set number of epochs
        self.config.max_epochs = num_epochs
        # statistics report
        self.report = None
        # model
        self.model = None


    def save(self, path):
        saved = torch.save(self.model.state_dict(), path)
        return saved

    def load(self):
        model = self.model_arch()
        model.load_state_dict(torch.load(path))
        model.eval()
        self.model = model

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
        # flatten predictions
        all_preds = np.array(all_preds).flatten()
        # f1, precision and recall
        report = TaggingReport(all_y, all_preds)
        # accuracy
        report.accuracy = accuracy_score(all_y, all_preds)
        return report


    def _prepare_data(self, data_sample):
        # TODO: replace with normal tokenizer
        # my first hacky tokenizer
        tokenizer = lambda sent: [x.strip() for x in sent.split(" ")]
        # Creating Field for data
        text_field = data.Field(sequential=True, tokenize=tokenizer, lower=True)
        label_field = data.Field(sequential=False, use_vocab=False)
        datafields = [("text", text_field), ("label", label_field)]
        # iterators to lists
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
        train_dataframe = pd.DataFrame({"text": texts, "label": labels})
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
        # training data iterator
        train_iterator = data.BucketIterator(
            (train_data),
            batch_size = self.config.batch_size,
            sort_key = lambda x: len(x.text),
            repeat = False,
            shuffle = True
        )
        # validation and test data iterator
        val_iterator, test_iterator = data.BucketIterator.splits(
            (val_data, test_data),
            batch_size=self.config.batch_size,
            sort_key=lambda x: len(x.text),
            repeat=False,
            shuffle=False)
        return train_iterator, val_iterator, test_iterator, text_field


    def train(self, data_sample):
        # prepare data
        train_iterator, val_iterator, test_iterator, text_field = self._prepare_data(data_sample)
        # declare model
        model = self.model_arch(self.config, len(text_field.vocab), text_field.vocab.vectors, self.evaluate_model)
        # check cuda
        if torch.cuda.is_available():
            model.cuda()
        # train
        model.train()
        optimizer = optim.SGD(model.parameters(), lr=self.config.lr)
        NLLLoss = nn.NLLLoss()
        model.add_optimizer(optimizer)
        model.add_loss_op(NLLLoss)
        # run epochs
        reports = []
        for i in range(self.config.max_epochs):
            report = model.run_epoch(train_iterator, val_iterator, i)
            reports.append(report)
        # set model statistics based on evaluation of last epoch
        self.report = reports[-1]
        # set model
        self.model = model
        return self.report
