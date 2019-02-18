import os
import json
from searcher.models import Search

class BaseWorker:

    def run(self, task_id):
        raise NotImplementedError("Worker should implement run method")

    @staticmethod
    def _parse_query(parameters):
        """
        Returns the query to be sent into elasticsearch depending on the Search
        being used. In case no search is selected, it returns a ready-made query
        to get all documents.

        :param parameters: Task parameters send from the form.
        :return: Query to be sent towards the ES instance.
        """
        search = parameters['search']
        # select search
        if search == 'all_docs':
            query = {"main": {"query": {"bool": {"minimum_should_match": 0, "must": [], "must_not": [], "should": []}}}}
        else:
            query = json.loads(Search.objects.get(pk=int(search)).query)
        return query