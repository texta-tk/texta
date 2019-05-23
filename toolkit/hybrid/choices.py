from toolkit.elastic.aggregator import ElasticCore

def get_fact_names():
    return [('TEEMA', 'TEEMA')]

HYBRID_TAGGER_CHOICES = {"min_freq": [(50,50), (100, 100), (250, 250), (500, 500), (1000, 1000)]}