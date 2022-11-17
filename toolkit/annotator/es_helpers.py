from typing import List
from texta_elastic.core import ElasticCore
from toolkit.annotator.choices import AnnotationType
from toolkit.elastic.index.models import Index
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
import json
import logging


TEXTA_FACTS_FIELD = "texta_facts"
TEXTA_ANNOTATOR_FIELD = "texta_annotator"
TEXTA_META_FIELD = "texta_meta"
TEXTA_UUID_FIELD = "document_uuid"
PROCESSED_TIMESTAMP_FIELD = "processed_timestamp_utc"

AGGS_TERM_NAME = "aggs_term"
AGGS_FACT_NAME = "aggs_fact"
AGGS_FACT_VALUE = "aggs_value"

def collect_doc_ids(scroll_batch: List[dict]) -> List[str]:
    """ Collects a list of document uuids from a batch of documents.
    """
    doc_ids = [
        doc["_source"][TEXTA_META_FIELD][TEXTA_UUID_FIELD]
        for doc in scroll_batch
    ]
    return doc_ids

def _get_doc_id_restriction(doc_ids: List[str]) -> dict:
    """ Restricts the query by document IDs.
    """
    restriction = {
        "terms": {
            f"{TEXTA_META_FIELD}.{TEXTA_UUID_FIELD}.keyword": doc_ids
        }
    }
    return restriction

def _get_is_annotated_restriction() -> dict:
    """ Restricts the query to documents that have been
    annotated / validated.
    """
    restriction = {
       "nested": {
          "path": TEXTA_ANNOTATOR_FIELD,
          "query": {
             "bool": {
                "must": [
                   {
                      "exists": {
                         "field": f"{TEXTA_ANNOTATOR_FIELD}.{PROCESSED_TIMESTAMP_FIELD}"
                      }
                   }
                ]
             }
          }
       }
    }
    return restriction

def get_filter_query(doc_ids: List[str], ignore_unannotated: bool = False) -> dict:
    """ Constructs a query for filtering documents based on their UUIDs.
    If `ignore_unannotated` is enabled, the query additionally returns only
    documents that have been either annotated or validated.
    """
    doc_id_restriction = _get_doc_id_restriction(doc_ids)
    query = {
        "query": {
            "bool": {
                "must": [
                    doc_id_restriction
                ]
            }
        }
    }
    if ignore_unannotated:
        # Restrict query to docs that have been annotated
        is_annotated_restriction = _get_is_annotated_restriction()
        query["query"]["bool"]["must"].append(is_annotated_restriction)
    return query

def get_nested_fact_aggregation_query() -> dict:
    """ Constructs a nested aggregation query that will:
    1. Aggregate over doc ID field
    2. Run a nested aggregation on fact_values
    """
    aggs_query = {
        AGGS_TERM_NAME: {
            "terms": {
                "field": f"{TEXTA_META_FIELD}.{TEXTA_UUID_FIELD}.keyword"
            },
            "aggs": {
                AGGS_FACT_NAME: {
                    "nested": {
                        "path": TEXTA_FACTS_FIELD
                    },
                    "aggs": {
                        AGGS_FACT_VALUE: {
                            "terms": {
                                "field": f"{TEXTA_FACTS_FIELD}.str_val"
                            }
                         }
                     }
                 }
            }
        }
    }
    return aggs_query


def generate_texta_fact(
        fact_name: str,
        fact_value: str,
        doc_path: str = "",
        spans: str = "",
        sent_index: int = 0,
        source: str = "annotator",
        author: str = "") -> dict:
    """ Generates a new Texta Fact.
    """

    if not spans:
        spans = json.dumps([[0,0]])

    new_fact = {
        "fact": fact_name,
        "str_val": fact_value,
        "doc_path": doc_path,
        "spans": spans,
        "sent_index": sent_index,
        "source": source,
        "author": author
    }
    return new_fact


def generate_merged_facts(
        fact_restrictions: dict,
        pos_count: int,
        pos_label: str,
        annotation_type: str,
        add_negatives: bool = True) -> List[dict]:

    """ Generates merged facts based on various count thresholds,
    true counts and annotation type.
    """
    new_facts = []

    for fact_restriction in fact_restrictions:

        min_agreements = fact_restriction.get("min_agreements")
        fact_name = fact_restriction.get("fact_name")
        new_fact = None

        if min_agreements <= pos_count:
            new_fact = generate_texta_fact(fact_name=fact_name, fact_value=pos_label)

        elif annotation_type == AnnotationType.BINARY.value and add_negatives:
            new_fact = generate_texta_fact(fact_name=fact_name, fact_value="false")

        if new_fact:
            new_facts.append(new_fact)
    return new_facts


def update_texta_facts(
        es_docs: List[dict],
        fact_restrictions: dict,
        pos_counts: dict,
        annotation_type: str,
        add_negatives: bool) -> List[dict]:
    """ Updates Texta Facts with merged facts.
    """
    updated_es_docs = []
    for doc in es_docs:
        facts = doc["_source"].get(TEXTA_FACTS_FIELD, [])
        doc_id = doc["_source"][TEXTA_META_FIELD][TEXTA_UUID_FIELD]
        if doc_id in pos_counts:
            pos_count_list = pos_counts[doc_id].items()
            for label, pos_count in pos_count_list:
                new_facts = generate_merged_facts(
                    fact_restrictions = fact_restrictions,
                    pos_count = pos_count,
                    pos_label = label,
                    annotation_type = annotation_type,
                    add_negatives=add_negatives
                )
                facts.extend(new_facts)
            doc["_source"][TEXTA_FACTS_FIELD] = facts
            updated_es_docs.append(doc)
    return updated_es_docs


def create_new_index(source_index: str, new_index: str) -> Index:
    """ Creates an empty index with otherwise the same mapping as the original source index,
    but adds texta_facts mapping (if not already present) and removes texta_annotator
    fields mapping.
    """

    ec = ElasticCore()

    logging.getLogger(INFO_LOGGER).info(f"Updating index schema for index '{new_index}'.")
    schema = ec.get_mapping(source_index).get(source_index).get("mappings")

    # Remove annotator fields from the schema
    schema.get("properties").pop(TEXTA_ANNOTATOR_FIELD, None)
    updated_schema = {"mappings": {"_doc": schema}}

    logging.getLogger(INFO_LOGGER).info(f"Creating a new index '{new_index}' with merged annotations.")

    # Create the new_index
    create_index_res = ec.create_index(new_index, updated_schema)

    # Add texta facts mapping in case the source index doesn't contain facts
    ec.add_texta_facts_mapping(new_index)

    index_model, is_created = Index.objects.get_or_create(name=new_index)

    return index_model
