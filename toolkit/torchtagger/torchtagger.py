from sklearn.metrics import accuracy_score
from torchtext.vocab import Vectors
import torch.optim as optim
from torchtext import data
from torch import nn
import pandas as pd
import numpy as np
import json
import torch
import dill

from toolkit.embedding.embedding import W2VEmbedding
from .torch_models.models import TORCH_MODELS
from toolkit.tagger.report import TaggingReport
from .models import TorchTagger as TorchTaggerObject

class TorchTagger:

    def __init__(self, tagger_id, model_arch="fastText", n_classes=2, num_epochs=5):
        # retrieve model and initial config
        self.config = TORCH_MODELS[model_arch]["config"]()
        self.model_arch = TORCH_MODELS[model_arch]["model"]
        # set number of output classes
        self.config.output_size = n_classes
        # set number of epochs
        self.config.max_epochs = num_epochs
        # statistics report for each epoch
        self.epoch_reports = []
        # model
        self.model = None
        self.text_field = None
        self.tagger_id = int(tagger_id)
        # indixes to save label to int relations
        self.label_index = None
        self.label_reverse_index = None
        # load tokenizer and embedding for the model
        self.tokenizer = self._get_tokenizer()
        self.embedding = self._get_embedding()


    def _get_tokenizer(self):
        # TODO: replace with normal tokenizer
        # my first hacky tokenizer
        return lambda sent: [x.strip() for x in sent.split(" ")]


    def _get_embedding(self):
        # load embedding
        tagger_object = TorchTaggerObject.objects.get(pk=self.tagger_id)
        embedding_model = W2VEmbedding(tagger_object.embedding.id)
        embedding_model.load()
        return embedding_model


    def save(self, path):
        """Saves model on disk."""
        torch.save(self.model, path)
        with open(f"{path}_text_field", "wb") as fh:
            dill.dump(self.text_field, fh)
        return True


    def load(self):
        """Loads model from disk."""
        tagger_object = TorchTaggerObject.objects.get(pk=self.tagger_id)
        tagger_path = tagger_object.model.path
        # load model
        model = torch.load(tagger_path)
        model.eval()
        # set tagger description & model
        self.description = tagger_object.description
        self.model = model
        # load & set field object
        with open(tagger_object.text_field.path, "rb") as fh:
            self.text_field = dill.load(fh)
        # set label reverse index used for prediction
        self.label_reverse_index = json.loads(tagger_object.label_index)
        return self.model


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


    def _get_examples_and_labels(self, data_sample):
        # lists for examples and labels
        examples = []
        labels = []
        # retrieve examples for each class
        for label, class_examples in data_sample.data.items():
            for example in class_examples:
                examples.append(example)
                labels.append(self.label_index[label])
        return examples, labels


    def _get_datafields(self):
        # Creating blank Fields for data
        text_field = data.Field(sequential=True, tokenize=self.tokenizer, lower=True)
        label_field = data.Field(sequential=False, use_vocab=False)
        # create Fields based on field names in document
        datafields = [("text", text_field), ("label", label_field)]
        return datafields, text_field


    def _prepare_data(self, data_sample):
        # retrieve vectors and vocab dict from embedding
        embedding_matrix, word2index = self.embedding.tensorize()
        # set embedding size according to the dimensionality embedding model
        embedding_size = len(embedding_matrix[0])
        self.config.embed_size = embedding_size
        # create label dicts for later lookup
        self.label_index = {a: i for i, a in enumerate(data_sample.data.keys())}
        self.label_reverse_index = {b: a for a, b in self.label_index.items()}
        # update output size to match number of classes
        self.config.output_size = len(list(data_sample.data.keys()))

        # retrieve examples and labels from data sample
        examples, labels = self._get_examples_and_labels(data_sample)
        # create datafields
        datafields, text_field = self._get_datafields()

        # create pandas dataframe and torchtext dataset
        train_dataframe = pd.DataFrame({"text": examples, "label": labels})
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
            # clear cuda cache prior to training
            torch.cuda.empty_cache()
        # train
        model.train()
        optimizer = optim.SGD(model.parameters(), lr=self.config.lr)
        NLLLoss = nn.NLLLoss()
        model.add_optimizer(optimizer)
        model.add_loss_op(NLLLoss)
        # run epochs
        for i in range(self.config.max_epochs):
            report = model.run_epoch(train_iterator, val_iterator, i)
            self.epoch_reports.append(report)
            print("Epoch:", i, report.to_dict())
        # set model
        self.model = model
        # set vocab
        self.text_field = text_field
        # return report for last epoch
        return report


    def tag_text(self, text, get_label=True):
        """
        Predicts on raw text.
        :return: class number, class probability
        """
        processed_text = self.text_field.process([self.text_field.preprocess(text)])
        if torch.cuda.is_available():
            processed_text = processed_text.to('cuda')
        prediction = self.model(processed_text)
        prediction_item = prediction.argmax().item()
        prediction_prob = prediction[0][prediction_item].item()
        # get class label if asked
        if get_label:
            prediction_item = self.label_reverse_index[str(prediction_item)]
        # TODO: should use some other metric for prob
        # because prob depends currently on number of classes
        return prediction_item, prediction_prob


    def tag_doc(self, doc):
        """
        Predicts on json document.
        :return: class number, class probability
        """
        # TODO: redo this function to use multiple fields correctly
        combined_text = []
        for v in doc.values():
            combined_text.append(v)
        combined_text = " ".join(combined_text)
        return self.tag_text(combined_text)
