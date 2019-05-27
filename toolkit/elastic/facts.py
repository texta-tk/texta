
class Fact:

    def __init__(self, name, val, fact_type='str', spans=[]):
        self.name = name
        self.val = val
        self.spans = spans
    
    


class Facts:

    def __init__(self):
        self.core = ElasticCore()
    
    def get_facts(self):
        pass