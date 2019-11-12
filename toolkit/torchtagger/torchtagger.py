import torch
from torchtext import data
from torchtext.vocab import Vectors
import pandas as pd

from .torch_models.text_cnn.model import TextCNN
from .torch_models.text_cnn.config import Config


class TorchTagger:

    def __init__(self, embedding_location):
        self.config = Config()
        self.embedding_location = embedding_location

    def train(self, data_sample):
        # my first hacky tokenizer
        tokenizer = lambda sent: [x.strip() for x in sent.split(" ")]

        # Creating Field for data
        text_field = data.Field(sequential=True, tokenize=tokenizer, lower=True, fix_length=self.config.max_sen_len)
        label_field = data.Field(sequential=False, use_vocab=False)
        datafields = [("text", text_field), ("label", label_field)]

        positives = list(data_sample.positives)
        negatives = list(data_sample.negatives)

        # combine samples and create labels
        texts = positives+negatives
        labels = [1]*len(positives)+[0]*len(negatives)

        # create pandas dataframe
        train_dataframe = pd.DataFrame({"texts": texts, "labels": labels})
        train_examples = [data.Example.fromlist(i, datafields) for i in train_dataframe.values.tolist()]
        train_data = data.Dataset(train_examples, datafields)
        # split training and testing data
        train_data, val_data = train_data.split(split_ratio=0.8)
        # build vocab
        text_field.build_vocab(train_data, vectors=Vectors(self.embedding_location))

        # Create Model with specified optimizer and loss function
        ##############################################################
        model = TextCNN(self.config, len(dataset.vocab), dataset.word_embeddings)
        if torch.cuda.is_available():
            model.cuda()
        model.train()
        optimizer = optim.SGD(model.parameters(), lr=config.lr)
        NLLLoss = nn.NLLLoss()
        model.add_optimizer(optimizer)
        model.add_loss_op(NLLLoss)
        ##############################################################

