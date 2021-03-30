import json
from typing import List

INNER_HITS_MAX_SIZE = 100


class Query:

    def __init__(self, operator="must"):
        self.query = {"query": {"bool": {"should": [], "must": [], "must_not": []}}}
        self.operator = operator


    def __str__(self):
        return json.dumps(self.query)


    def __dict__(self):
        return self.query

    def add_sub_query(self, sub_query):
        self.query["query"]["bool"][self.operator].append(sub_query["query"])

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


    def add_facts_filter(self, fact_names: List[str], fact_values: List[str] = [], operator: str="must", filter_id: int=1):
        """
        Adds facts filter to the query. Fact values are optional, but if added
        len(fact_values) should equal len(fact_names) and fact value in position i
        should correspond to fact name in position i.

        :param fact_names: List of fact names to use for restricting the query.
        :param fact_values: List of fact values (corresponding to the fact names on
                            the same position) to use for restricting the query.
        :param operator: Operator used for joining the facts in the query.
        """
        self.query["query"]["bool"][self.operator].append({"bool": {operator:[]}})
        for i, fact_name in enumerate(fact_names):
            new_restriction = {
                "nested": {
                    "path": "texta_facts",
                    "inner_hits": {
                        "name": "fact_filter_{}".format(filter_id+i),
                        "size": INNER_HITS_MAX_SIZE
                    },
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"texta_facts.fact": fact_name}},
                            ]
                        }
                    }
                }
            }
            if fact_values:
                fact_value = fact_values[i]
                if fact_value:
                    new_restriction["nested"]["query"]["bool"]["must"].append({"match": {"texta_facts.str_val": fact_value}})
            self.query["query"]["bool"]["must"][0]["bool"][operator].append(new_restriction)


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
