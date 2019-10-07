from collections import OrderedDict
from psutil import virtual_memory
from time import time

from toolkit.tools.logger import Logger

class ModelCache:
    """
    Cache to hold recently used Tagger & Embedding objects in memory.
    """
    def __init__(self, object_class, cache_duration=1800, memory_limit=20.0):
        self.models = {}
        self.object_class = object_class
        self.cache_duration = cache_duration
        self.memory_limit = memory_limit


    def get_model(self, model_id):
        # check memory availability
        self.check_memory()
        # load model if not in cache
        try:
            if model_id not in self.models:
                model = self.object_class(model_id)
                model.load()
                self.models[model_id] = {"model": model, "last_access": time()}
            # update last access timestamp & remove old models
            self.models[model_id]["last_access"] = time()
            self.clean_cache()
            # return model
            return self.models[model_id]["model"]
        except Exception as e:
            Logger().error("Error loading models.", execution_info=e)
            return None
    

    def clean_cache(self):
        # removes models not accessed in last 60 minutes (default)
        self.models = {k:v for k,v in self.models.items() if v["last_access"] >= time()-self.cache_duration}


    def check_memory(self):
        """
        Checks memory availability and flushes cache if memory full.
        """
        free_percentage = self._mem_free_percentage()
        # if less than memory_limit % free, flush the models to make room for more
        if free_percentage < self.memory_limit:
            Logger().info(f"Memory almost full ({free_percentage} percent free). Releasing memory by flushing models.")
            self.models = {}
            # check again to see how much memory we gained
            free_percentage = _mem_free_percentage()
            Logger().info(f"Models successfully flushed. {free_percentage} percent free.")


    @staticmethod
    def _mem_free_percentage():
        memory = virtual_memory()
        free_percentage = (float(memory.available)/float(memory.total))*100
        return free_percentage
