import json

INNER_HITS_MAX_SIZE = 100


class Query:

    def __init__(self):
        self.query = {"query": {"bool": {"should": [], "must": [], "must_not": []}}}

    def __str__(self):
        return json.dumps(self.query)
    
    def __dict__(self):
        return self.query

    def add_fact_filter(self, fact_name, fact_value, filter_id=1):
        """
        Add fact filter to existing query.
        """
        query = {"nested": {
                    "path": "texta_facts",
                    "inner_hits": {
                        "name": "fact_filter_{}".format(filter_id),
                        "size": INNER_HITS_MAX_SIZE
                    },
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"texta_facts.fact": fact_name}},
                                {"match": {"texta_facts.str_val": fact_value}}
                            ]
                        }
                    }
                }
            }
        
        self.query["query"]["bool"]["must"].append(query)


    def add_mlt(self, mlt_fields, text):
        """
        Add More Like This query.
        """
        mlt_query = {"fields": mlt_fields, "like": text, "min_term_freq": 1, "max_query_terms": 12}
        self.query["query"]["more_like_this"] = mlt_query

