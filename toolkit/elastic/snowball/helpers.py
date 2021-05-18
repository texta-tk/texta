import logging
from typing import List

from texta_mlp.document import Document
from texta_mlp.mlp import MLP

from toolkit.elastic.choices import map_iso_to_snowball
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import INFO_LOGGER, MLP_MODEL_DIRECTORY
from toolkit.tools.lemmatizer import ElasticLemmatizer


def apply_stemmer_to_texts(texts: List[str], mlp: MLP, detect_lang: bool = False, stemmer_lang: str = None):
    lemmatizer = ElasticLemmatizer(language=None)
    processed_texts = []
    for text in texts:
        if detect_lang:
            lang = mlp.detect_language(text)
            lang = map_iso_to_snowball(lang)
            if lang:
                stemmed_text = lemmatizer.lemmatize(text, language=lang)
            else:
                stemmed_text = text
        elif stemmer_lang:
            stemmed_text = lemmatizer.lemmatize(text, language=stemmer_lang)
        processed_texts.append(stemmed_text)
    return processed_texts


def process_stemmer_actions(generator: ElasticSearcher, worker, detect_lang: bool, snowball_language: str, fields_to_parse: List[str]):
    counter = 0
    info_logger = logging.getLogger(INFO_LOGGER)
    mlp = MLP(
        language_codes=[],
        resource_dir=MLP_MODEL_DIRECTORY,
        logging_level="info"
    )

    info_logger.info(f"Applying stemming to the worker with an ID of {worker.pk}!")
    for document_batch in generator:
        for item in document_batch:
            # This will be a list of texts.
            source = item["_source"]
            for field in fields_to_parse:
                texts = mlp.parse_doc_texts(doc_path=field, document=source)
                stemmed_texts = apply_stemmer_to_texts(texts, mlp, detect_lang, stemmer_lang=snowball_language)
                if stemmed_texts:
                    text = stemmed_texts[0]
                    new_field = f"{field}_mlp.stem"
                    source = Document.edit_doc(source, new_field, text)

            elastic_update_body = {
                "_id": item["_id"],
                "_index": item["_index"],
                "_type": item.get("_type", "_doc"),
                "_op_type": "update",
                "retry_on_conflict": 3,
                "doc": source
            }

            yield elastic_update_body

            counter += 1
            progress = generator.callback_progress
            if counter % generator.scroll_size == 0:
                info_logger.info(f"Progress on applying language detection for worker with id: {worker.pk} at {counter} out of {progress.n_total} documents!")
            elif counter == progress.n_total:
                info_logger.info(f"Finished applying language detection for worker with id: {worker.pk} at {counter}/{progress.n_total} documents!")
