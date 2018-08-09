import os
import shutil
import threading
from collections import defaultdict
from time import sleep,time

import gensim
import traceback

from .gensim_wrapper.masked_word2vec import MaskedWord2Vec

from texta.settings import USER_MODELS, MODELS_DIR


try:
   import cPickle as pickle
except ImportError as e:
   import pickle

class NegativesEntry:

    def __init__(self,negatives):
        self.negatives = negatives
        self.access_time = time()

class ModelEntry:

    def __init__(self,model):
        self.model = model
        self.access_time = time()

class ModelManager(threading.Thread):

    def __init__(self,expiration_time,refresh_time,models=None):
        threading.Thread.__init__(self)
        self.daemon = True
        self._model_negatives = defaultdict(lambda: defaultdict(dict))
        self._models = {}
        self.expiration_time = expiration_time
        self.refresh_time = refresh_time
        self.to_be_deleted_negatives = []
        self.to_be_deleted_models = []
        self._negatives_lock = threading.Lock()
        self._models_lock = threading.Lock()
        self._negatives_lock = threading.Lock()
        self._stop = threading.Event()

    def run(self):
        while not self.stopped():
            self._remove_expired_negatives()
            sleep(self.refresh_time)

    def _remove_expired_negatives(self):
        # TODO remove empty entries and dirs
        with self._negatives_lock and self._models_lock:
            for model_name in self._model_negatives:
                for username in self._model_negatives[model_name]:
                    for lexicon in self._model_negatives[model_name][username]:
                        if time() - self._model_negatives[model_name][username][lexicon].access_time >= self.expiration_time:
                            self.to_be_deleted_negatives.append((model_name,username,lexicon))

            for deleted_negative in self.to_be_deleted_negatives:
                if len(deleted_negative) == 4:
                    # lexicon removed
                    if deleted_negative[2] in self._model_negatives[deleted_negative[0]][deleted_negative[1]]:
                        del self._model_negatives[deleted_negative[0]][deleted_negative[1]][deleted_negative[2]]
                    negatives_path = os.path.join(USER_MODELS,deleted_negative[0],deleted_negative[1],"lexicon_%d_negatives.pickle"%deleted_negative[2])
                    if os.path.exists(negatives_path):
                        # TODO! path does not seem to be defined. KOM should check this out.
                        os.remove(negatives_path)
                elif len(deleted_negative) == 3:
                    # negatives expired
                    if deleted_negative[2] in self._model_negatives[deleted_negative[0]][deleted_negative[1]]:
                        del self._model_negatives[deleted_negative[0]][deleted_negative[1]][deleted_negative[2]]

            self.to_be_deleted_negatives = []

            for model_name in self._models:
                if time() - self._models[model_name].access_time >= self.expiration_time:
                    self.to_be_deleted_models.append((model_name,'expired'))

            for deleted_model,reason in self.to_be_deleted_models:
                if reason == 'removed':
                    if deleted_model in self._models:
                        model_path = os.path.join(MODELS_DIR,"model_%s"%deleted_model)
                        if os.path.exists(model_path):
                            os.remove(model_path)

                    if deleted_model in self._model_negatives:
                        negatives_path = os.path.join(USER_MODELS,model_name)
                        if os.path.exists(negatives_path):
                            shutil.rmtree(negatives_path)

                if deleted_model in self._models:
                    del self._models[deleted_model]
                if deleted_model in self._model_negatives:
                    del self._model_negatives[deleted_model]

            self.to_be_deleted_models = []


    def remove_model(self,model_name):
        with self._negatives_lock:
            self.to_be_deleted_models.append((str(model_name),'removed'))

    def get_model(self,model_name):
        with self._models_lock:
            if model_name not in self._models:
                model_path = os.path.join(MODELS_DIR,"model_%s"%model_name)
                if os.path.exists(model_path):
                    self._models[model_name] = ModelEntry(MaskedWord2Vec(gensim.models.Word2Vec.load(model_path)))
                else:
                    raise LookupError("Model %s not found."%model_name)

            self._models[model_name].access_time = time()
            return self._models[model_name].model



    def get_negatives(self,model_name,username,lexicon_id):
        model_name = str(model_name)
        with self._negatives_lock:
            if lexicon_id not in self._model_negatives[model_name][username]:
                negatives_path = os.path.join(USER_MODELS,model_name,username,"lexicon_%d_negatives.pickle"%lexicon_id)
                if os.path.exists(negatives_path):
                    with open(negatives_path,'rb') as fin:
                        self._model_negatives[model_name][username][lexicon_id] = NegativesEntry(pickle.loads(fin.read().strip()))
                else:
                    self._model_negatives[model_name][username][lexicon_id] = NegativesEntry([])

            self._model_negatives[model_name][username][lexicon_id].access_time = time()
            return self._model_negatives[model_name][username][lexicon_id].negatives

    def save_negatives(self,model_name,username,lexicon_id):
        model_name = str(model_name)
        with self._negatives_lock:
            if lexicon_id in self._model_negatives[model_name][username]:
                negatives_dir = os.path.join(USER_MODELS,model_name,username)
                negatives_path = os.path.join(negatives_dir,"lexicon_%d_negatives.pickle"%lexicon_id)

                try:
                    os.makedirs(negatives_dir)
                except:
                    OSError

                with open(negatives_path,'wb') as fout:
                    fout.write(pickle.dumps(self._model_negatives[model_name][username][lexicon_id].negatives))

                self._model_negatives[model_name][username][lexicon_id].access_time = time()

    def reset_negatives(self,model_name,username,lexicon_id):
        model_name = str(model_name)
        with self._negatives_lock:
            if lexicon_id in self._model_negatives[model_name][username]:
                self._model_negatives[model_name][username][lexicon_id].negatives = []
                self._model_negatives[model_name][username][lexicon_id].access_time = time()
            negatives_path = os.path.join(USER_MODELS,model_name,username,"lexicon_%s_negatives.pickle"%lexicon_id)

            if os.path.exists(negatives_path):
                os.remove(negatives_path)

    def remove_negatives(self,model_name,username,lexicon_id):
        model_name = str(model_name)
        # when removing lexicon
        with self._negatives_lock:
            self.to_be_deleted_negatives.append((model_name,username,lexicon_id,'erase'))

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()



def get_model_manager(expiration_time=300,refresh_time=60,models=None):
    model_manager = ModelManager(expiration_time,refresh_time,models)
    model_manager.start()
    return model_manager

if __name__ == "__main__":
    mm = get_model_manager(expiration_time=10,refresh_time=4)
    mm.get_negatives('model1','kom',1)
    sleep(6)
    mm.get_negatives('model1','kom',1)
    mm.get_negatives('model2','kom',2)
    sleep(6)
    mm.get_negatives('model2','kom',2)
    sleep(15)
