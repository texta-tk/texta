from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query    


class TagLogicViews():
    '''Re-usable logic for when a view needs to deal with facts'''

    def get_tags(self, fact_name, active_project, min_count=1000, max_count=None):
        """
        Finds possible tags for training by aggregating active project's indices.
        """
        active_indices = list(active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def create_queries(self, fact_name, tags):
        """
        Creates queries for finding documents for each tag.
        """
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries
