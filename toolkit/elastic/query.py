
class QueryFilter:

    def __init__(self, filter_field, filter_type, filter_content):
        self.field = filter_field
        self.type = filter_type
        self.content = filter_content


class Query:

    def __init__(self):
        self.query = {"query": {}}

    def __str__(self):
        return self.query

    def add_filter(self, query_filter):
        """
        Add filter to existing query.
        """
        # add bool object if not present
        if "bool" not in self.query["query"]:
            self.query["query"]["bool"] = {"should": [], "must": [], "must_not": []}
        
        #add filters here


    def add_mlt(self, mlt_fields, text):
        """
        Add More Like This query.
        """
        mlt_query = {"fields": mlt_fields, "like": text, "min_term_freq": 1, "max_query_terms": 12}
        self.query["query"]["more_like_this"] = mlt_query


