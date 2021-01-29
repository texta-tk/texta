from typing import List

from texta_mlp.mlp import MLP

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.searcher import ElasticSearcher


def process_actions(generator: ElasticSearcher, analyzers: List[str], field_data: List[str], mlp: MLP):
    # ElasticSearcher returns a list of 100 RAW elastic documents.
    # Since MLP needs a raw document to process, we need to memorize the index
    # of the document in question so that we could later fetch it's metadata for the Bulk generator.
    for documents in generator:

        document_sources = [dict(hit["_source"]) for hit in documents]
        mlp_processed = mlp.process_docs(document_sources, analyzers=analyzers, doc_paths=field_data)

        for index, mlp_processed_document in enumerate(mlp_processed):
            original_elastic_document = documents[index]

            original_facts = original_elastic_document["_source"].get("texta_facts", [])
            new_facts = mlp_processed_document.get("texta_facts", [])
            total_facts = [fact for fact in original_facts + new_facts if fact]
            unique_facts = ElasticDocument.remove_duplicate_facts(total_facts)

            elastic_update_body = {
                "_id": original_elastic_document["_id"],
                "_index": original_elastic_document["_index"],
                "_type": original_elastic_document.get("_type", "_doc"),
                "_op_type": "update",
                "doc": {**mlp_processed_document, **{"texta_facts": unique_facts}}
            }

            yield elastic_update_body
