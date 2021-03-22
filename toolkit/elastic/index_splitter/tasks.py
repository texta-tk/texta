import copy
import json
import logging

from celery.decorators import task

from toolkit.base_tasks import TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.elastic.index_splitter.models import IndexSplitter
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.mapping_tools import update_field_types, update_mapping
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


FLATTEN_DOC = False


def elastic_random_split_generator(generator, ratio, train_ix: str, test_ix: str):
    docs_count = generator.count()

    for ix, document in enumerate(generator):
        if (ix % 100 == 0):
            to_test_until = ix + min(ratio, (docs_count - ix) * (ratio / 100))
        if (ix < to_test_until):
            yield {
                "_index": test_ix,
                "_type": "_doc",
                "_source": document
            }
        else:
            yield {
                "_index": train_ix,
                "_type": "_doc",
                "_source": document
            }


def elastic_original_split_generator(generator, ratio, fact_name, fact_value, labels_distribution, train_ix: str, test_ix: str):
    test_index_quantities = {}
    for key, value in labels_distribution.items():
        if fact_value != "":
            if (key == fact_value):
                test_index_quantities[key] = round((ratio / 100) * value)
        else:
            test_index_quantities[key] = round((ratio / 100) * value)

    for document in generator:
        if fact_value == "":
            label = [fact["str_val"] for fact in document.get("texta_facts", []) if fact["fact"] == fact_name][0]
        else:
            label = [fact["str_val"] for fact in document.get("texta_facts", []) if (fact["fact"] == fact_name and fact["str_val"] == fact_value)][0]

        if (label in test_index_quantities and test_index_quantities[label] > 0):
            test_index_quantities[label] -= 1
            yield {
                "_index": test_ix,
                "_type": "_doc",
                "_source": document
            }
        else:
            yield {
                "_index": train_ix,
                "_type": "_doc",
                "_source": document
            }


def elastic_equal_split_generator(generator, test_size, fact_name, fact_value, labels_distribution, train_ix: str, test_ix: str):
    test_index_quantities = {}
    for key, _ in labels_distribution.items():
        if fact_value != "":
            if (key == fact_value):
                test_index_quantities[key] = 0
        else:
            test_index_quantities[key] = 0

    for document in generator:
        if fact_value == "":
            label = [fact["str_val"] for fact in document["texta_facts"] if fact["fact"] == fact_name][0]
        else:
            label = [fact["str_val"] for fact in document["texta_facts"] if (fact["fact"] == fact_name and fact["str_val"] == fact_value)][0]

        if (test_index_quantities[label] < test_size):
            test_index_quantities[label] += 1
            yield {
                "_index": test_ix,
                "_type": "_doc",
                "_source": document
            }
        else:
            yield {
                "_index": train_ix,
                "_type": "_doc",
                "_source": document
            }


@task(name="index_splitting_task", base=TransactionAwareTask)
def index_splitting_task(index_splitting_task_id):
    indexsplitter_obj = IndexSplitter.objects.get(pk=index_splitting_task_id)
    task_object = indexsplitter_obj.task
    indices = indexsplitter_obj.get_indices()
    fields = json.loads(indexsplitter_obj.fields)
    test_size = indexsplitter_obj.test_size
    scroll_size = indexsplitter_obj.scroll_size
    test_index = indexsplitter_obj.test_index
    train_index = indexsplitter_obj.train_index
    query = indexsplitter_obj.get_query()
    fact_name = indexsplitter_obj.fact
    fact_value = indexsplitter_obj.str_val
    distribution = indexsplitter_obj.distribution

    try:
        ''' for empty field post, use all posted indices fields '''
        if not fields:
            fields = ElasticCore().get_fields(indices)
            fields = [field["path"] for field in fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        # Use it just to insert data to elasticsearch. Index name does not matter. 
        elastic_doc = ElasticDocument(train_index)

        logging.getLogger(INFO_LOGGER).info("Updating indices schema.")
        schema_input = update_field_types(indices, fields, [], flatten_doc=FLATTEN_DOC)
        train_schema = update_mapping(schema_input, train_index, True)
        test_schema = update_mapping(schema_input, test_index, True)

        logging.getLogger(INFO_LOGGER).info("Creating new index.")
        # Creating new indices.
        _ = ElasticCore().create_index(train_index, train_schema)
        _ = ElasticCore().create_index(test_index, test_schema)

        if (distribution == LABEL_DISTRIBUTION[0][0]):  # random
            logging.getLogger(INFO_LOGGER).info("Splitting documents randomly.")

            elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
            actions = elastic_random_split_generator(elastic_search, test_size, train_index, test_index)

            # Since the index name is specified in the generator already, we can use either one of the ElasticDocument object.
            elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")

        else:
            # TODO: Must ensure that there is only a single fact with given fact name associated with each document
            # otherwise cannot guarantee equal distribution.

            if fact_value == "":
                fact_filter_query = {"query": {"nested": {"path": "texta_facts",
                                                          "query": {"bool": {"must": [{"term": {"texta_facts.fact": fact_name}}]}}}}}
            else:
                fact_filter_query = {'query': {'nested': {'path': 'texta_facts',
                                                          'query': {'bool': {'must': [{'term': {'texta_facts.fact': fact_name}},
                                                                                      {'term': {'texta_facts.str_val': fact_value}}]}}}}}

            # Concatenate input query with fact filtering query.
            filtered_query = {"query": {"bool": {"must": [query["query"],
                                                          fact_filter_query["query"]]}}}

            elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=filtered_query, scroll_size=scroll_size)

            aggregator = ElasticAggregator(indices=indices, query=copy.deepcopy(filtered_query))
            labels_distribution = aggregator.get_fact_values_distribution(fact_name)

            if (distribution == LABEL_DISTRIBUTION[1][0]):  # original

                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving original label distribution.")

                actions = elastic_original_split_generator(elastic_search, test_size, fact_name, fact_value, labels_distribution, train_index, test_index)
                elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")

            elif (distribution == LABEL_DISTRIBUTION[2][0]):  # equal

                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving equal label distribution.")

                actions = elastic_equal_split_generator(elastic_search, test_size, fact_name, fact_value, labels_distribution, train_index, test_index)
                elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")

            elif (distribution == LABEL_DISTRIBUTION[3][0]):  # custom

                custom_distributon = indexsplitter_obj.get_custom_distribution()

                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving custom label distribution.")

                # use original split generator but with ratio == 100
                # we don't use fact value here even if it's given because we have a custom distribution
                actions = elastic_original_split_generator(elastic_search, 100, fact_name, "", custom_distributon, train_index, test_index)
                elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")

        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info("Index splitting succesfully completed.")
    return True
