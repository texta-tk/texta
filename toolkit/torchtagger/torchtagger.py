import torch
from torchtext import data
from torchtext.vocab import Vectors
import pandas as pd


class Config(object):
    embed_size = 300
    num_channels = 100
    kernel_size = [3,4,5]
    output_size = 4
    max_epochs = 15
    lr = 0.3
    batch_size = 64
    max_sen_len = 30
    dropout_keep = 0.8


class TorchTagger:

    def __init__(self):
        self.config = Config()

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

        print(train_data)