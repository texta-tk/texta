import json

INNER_HITS_MAX_SIZE = 100


class Query:

    def __init__(self, operator="must"):
        self.query = {"query": {"bool": {"should": [], "must": [], "must_not": []}}}
        self.operator = operator

    def __str__(self):
        return json.dumps(self.query)

    def __dict__(self):
        return self.query

    def add_fact_filter(self, fact_name, fact_value, filter_id=1):
        """
        Adds fact filter to existing query.
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

        self.query["query"]["bool"][self.operator].append(query)

    def add_mlt(self, mlt_fields, text):
        """
        Adds More Like This query.
        """
        mlt_query = {"more_like_this": {"fields": mlt_fields, "like": text, "min_term_freq": 1, "max_query_terms": 12}}
        self.query["query"] = mlt_query

    def add_string_filter(self, query_string, match_type="match", fields=None):
        """
        Adds string filter to the query.
        """
        string_matching_query = {"multi_match": {"query": query_string}}
        if fields:
            string_matching_query["multi_match"]["fields"] = fields
        if match_type in ("phrase", "phrase_prefix"):
            string_matching_query["multi_match"]["type"] = match_type
        self.query["query"]["bool"][self.operator].append(string_matching_query)
