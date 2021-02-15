import json
import logging
from collections import defaultdict

from celery.decorators import task

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.mapping_generator import SchemaGenerator
from toolkit.elastic.models import Reindexer, IndexSplitter
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.tools.show_progress import ShowProgress
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER


""" TODOs:
    unique name problem and testing it.
"""

# TODO: add this to reindex task params
FLATTEN_DOC = False


def get_selected_fields(indices, fields):
    # get all fields in given indices
    all_fields = ElasticCore().get_fields(indices)
    # filter out selected fields
    selected_fields = [field for field in all_fields if field["path"] in fields]
    return selected_fields


def add_nested(fields):
    for field in fields:
        if '.' in field['path']:
            field['type'] = 'nested'
    return fields


def reformat_for_schema_generator(fields, flatten_doc=False):
    if not flatten_doc:
        fields = add_nested(fields)
    formatted_fields = defaultdict(list)
    for field in fields:
        if field['path'] == 'texta_facts':
            formatted_fields['texta_facts'].append('texta_facts')
        else:
            formatted_fields[field['type']].append(field['path'])
    return dict(formatted_fields)


def update_field_types(indices, fields, field_type, flatten_doc=False):
    ''' if fieldtype, for field named fieldtype change its type'''

    # returns fields edited by serializer input
    my_fields = get_selected_fields(indices, fields)
    my_field_data = [field["path"] for field in my_fields]

    for item in field_type:
        if item['path'] in my_field_data:
            field_to_edit = item['path']
            new_type = item['field_type']

            for field in my_fields:
                if field['path'] == field_to_edit:
                    field['type'] = new_type
                    # TODO must work, also when only name is changed
                    if 'new_path_name' in item.keys():
                        new_path_name = item['new_path_name']
                        field['path'] = new_path_name
    updated_field_types = reformat_for_schema_generator(my_fields, flatten_doc)
    return updated_field_types


def update_mapping(schema_input, doc_type: str, add_facts_mapping):
    mod_schema = SchemaGenerator().generate_schema(schema_input, add_facts_mapping)
    return {'mappings': {"_doc": mod_schema}}


def unflatten_doc(doc):
    """ Unflatten document retrieved from ElasticSearcher.
    """
    unflattened_doc = {}
    nested_fields = [(k, v) for k, v in doc.items() if '.' in k]
    not_nested_fields = {k: v for k, v in doc.items() if '.' not in k}
    unflattened_doc.update(not_nested_fields)
    for k, v in nested_fields:
        layers = k.split('.')
        for i, layer in enumerate(layers):
            if i == 0:
                if layer not in unflattened_doc:
                    unflattened_doc[layer] = {}
                nested_branch = unflattened_doc
            elif i < len(layers) - 1:
                if layer not in nested_branch[layers[i - 1]]:
                    nested_branch[layers[i - 1]][layer] = {}
                nested_branch = nested_branch[layers[i - 1]]
            else:
                if layer not in nested_branch[layers[i - 1]]:
                    nested_branch[layers[i - 1]][layer] = v
                nested_branch = nested_branch[layers[i - 1]]
    return unflattened_doc


def apply_elastic_search(elastic_search, flatten_doc=False):
    for document in elastic_search:
        new_doc = document
        if not flatten_doc:
            new_doc = unflatten_doc(new_doc)

        yield new_doc


def reindexer_bulk_generator(generator, index: str):
    for document in generator:
        yield {
            "_index": index,
            "_type": "_doc",
            "_source": document
        }

def elastic_random_split_generator(generator, ratio, train_ix: str, test_ix: str):
    docs_count = generator.count()

    for ix, document in enumerate(generator):
        if(ix % 100 == 0):
            to_test_until = ix + min(ratio, (docs_count-ix)*(ratio/100))
        if(ix < to_test_until):
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
            if(key == fact_value):
                test_index_quantities[key] = round((ratio/100)*value)
        else:
            test_index_quantities[key] = round((ratio/100)*value)

    for document in generator:
        if fact_value == "":
            label = [fact["str_val"] for fact in document["texta_facts"] if fact["fact"] == fact_name][0]
        else:
            label = [fact["str_val"] for fact in document["texta_facts"] if (fact["fact"] == fact_name and fact["str_val"] == fact_value)][0]
        
        if(label in test_index_quantities and test_index_quantities[label] > 0):
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
            if(key == fact_value):
                test_index_quantities[key] = 0
        else:
            test_index_quantities[key] = 0

    for document in generator:
        if fact_value == "":
            label = [fact["str_val"] for fact in document["texta_facts"] if fact["fact"] == fact_name][0]
        else:
            label = [fact["str_val"] for fact in document["texta_facts"] if (fact["fact"] == fact_name and fact["str_val"] == fact_value)][0]

        if(test_index_quantities[label] < test_size):
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

def bulk_add_documents(elastic_search: ElasticSearcher, elastic_doc: ElasticDocument, index: str, chunk_size: int, flatten_doc=False):
    new_docs = apply_elastic_search(elastic_search, flatten_doc)
    actions = reindexer_bulk_generator(new_docs, index)
    # No need to wait for indexing to actualize, hence refresh is False.
    elastic_doc.bulk_add_generator(actions=actions, chunk_size=chunk_size, refresh="wait_for")


@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id):
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = json.loads(reindexer_obj.fields)
    random_size = reindexer_obj.random_size
    field_type = json.loads(reindexer_obj.field_type)
    scroll_size = reindexer_obj.scroll_size
    new_index = reindexer_obj.new_index
    query = reindexer_obj.query

    logging.getLogger(INFO_LOGGER).info("Starting task 'reindex'.")

    try:
        ''' for empty field post, use all posted indices fields '''
        if not fields:
            fields = ElasticCore().get_fields(indices)
            fields = [field["path"] for field in fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
        elastic_doc = ElasticDocument(new_index)

        if random_size > 0:
            elastic_search = ElasticSearcher(indices=indices, field_data=fields, query=query, scroll_size=scroll_size).random_documents(size=random_size)

        logging.getLogger(INFO_LOGGER).info("Updating index schema.")
        ''' the operations that don't require a mapping update have been completed '''
        schema_input = update_field_types(indices, fields, field_type, flatten_doc=FLATTEN_DOC)
        updated_schema = update_mapping(schema_input, new_index, reindexer_obj.add_facts_mapping)

        logging.getLogger(INFO_LOGGER).info("Creating new index.")
        # create new_index
        create_index_res = ElasticCore().create_index(new_index, updated_schema)

        logging.getLogger(INFO_LOGGER).info("Indexing documents.")
        # set new_index name as mapping name, perhaps make it customizable in the future
        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=FLATTEN_DOC)

        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info("Reindexing succesfully completed.")
    return True

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

        if(distribution == LABEL_DISTRIBUTION[0][0]): #random
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

            aggregator = ElasticAggregator(indices=indices, query=filtered_query)
            labels_distribution = aggregator.get_fact_values_distribution(fact_name)
        
            if(distribution == LABEL_DISTRIBUTION[1][0]): #original
            
                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving original label distribution.")

                actions = elastic_original_split_generator(elastic_search, test_size, fact_name, fact_value, labels_distribution, train_index, test_index)
                elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")

            elif(distribution == LABEL_DISTRIBUTION[2][0]): #equal

                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving equal label distribution.")
            
                actions = elastic_equal_split_generator(elastic_search, test_size, fact_name, fact_value, labels_distribution, train_index, test_index)
                elastic_doc.bulk_add_generator(actions=actions, chunk_size=scroll_size, refresh="wait_for")
        
            elif(distribution == LABEL_DISTRIBUTION[3][0]): #custom

                custom_distributon = indexsplitter_obj.get_custom_distribution()

                logging.getLogger(INFO_LOGGER).info("Splitting documents while preserving custom label distribution.")

                #use original split generator but with ratio == 100
                #we don't use fact value here even if it's given because we have a custom distribution
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