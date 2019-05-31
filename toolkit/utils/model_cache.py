from time import time

class ModelCache:
    """
    Cache to hold recently used Tagger & Embedding objects in memory.
    """
    def __init__(self, object_class):
        self.models = {}
        self.object_class = object_class


    def get_model(self, model_id):
        # load model if not in cache
        if model_id not in self.models:
            model = self.object_class(model_id)
            model.load()
            self.models[model_id] = {'model': model, 'last_access': time()}
        
        # update last access timestamp
        self.models[model_id]['last_access'] = time()

        return self.models[model_id]['model']
