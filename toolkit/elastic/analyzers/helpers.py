import logging
from typing import List

from texta_elastic.searcher import ElasticSearcher
from texta_mlp.document import Document
from texta_mlp.mlp import MLP

from toolkit.elastic.choices import map_iso_to_snowball
from toolkit.mlp.helpers import parse_doc_texts
from toolkit.settings import INFO_LOGGER, MLP_MODEL_DIRECTORY
from toolkit.tools.lemmatizer import ElasticAnalyzer


def apply_stemming(texts: List[str], mlp: MLP, strip_html: bool, detect_lang: bool = False, stemmer_lang: str = None, tokenizer="standard"):
    analyzer = ElasticAnalyzer(language=None)
    processed_texts = []
    # Initiate this here so a value would always be passed to return in case
    # there are no texts. Should be useful for most single-text cases.
    lang = stemmer_lang

    for text in texts:
        if detect_lang:
            lang = mlp.detect_language(text)
            lang = map_iso_to_snowball(lang)
            analyzed_text = analyzer.stem_text(text, language=lang, strip_html=strip_html, tokenizer=tokenizer) if lang else text
        else:
            analyzed_text = analyzer.stem_text(text, language=stemmer_lang, strip_html=strip_html, tokenizer=tokenizer)

        processed_texts.append(analyzed_text)
    return processed_texts, lang


def apply_tokenization(texts: List[str], tokenizer: str = "standard"):
    analyzer = ElasticAnalyzer(language=None)
    processed_texts = []
    for text in texts:
        analyzed_text = analyzer.tokenize_text(text, tokenizer=tokenizer, strip_html=True)
        processed_texts.append(analyzed_text)
    return processed_texts


def process_analyzer_actions(
        generator: ElasticSearcher,
        worker,
        detect_lang: bool,
        snowball_language: str,
        fields_to_parse: List[str],
        analyzers: List[str],
        tokenizer: str,
        strip_html: bool
):
    counter = 0
    info_logger = logging.getLogger(INFO_LOGGER)
    mlp = MLP(
        language_codes=[],
        resource_dir=MLP_MODEL_DIRECTORY,
        logging_level="info"
    )

    info_logger.info(f"Applying analyzers to the worker with an ID of {worker.pk}!")
    for document_batch in generator:
        for item in document_batch:
            # This will be a list of texts.
            source = item["_source"]
            for field in fields_to_parse:
                texts = parse_doc_texts(doc_path=field, document=source)
                if "stemmer" in analyzers:
                    stemmed_texts, lang = apply_stemming(texts, mlp=mlp, strip_html=strip_html, detect_lang=detect_lang, stemmer_lang=snowball_language, tokenizer=tokenizer)
                    if stemmed_texts:
                        text = stemmed_texts[0]
                        new_field = f"{field}_es.stems"
                        source = Document.edit_doc(source, new_field, text)
                        source = Document.edit_doc(source, f"{field}_es.stem_lang", lang)

                if "tokenizer" in analyzers:
                    tokenized_texts = apply_tokenization(texts, tokenizer=tokenizer)
                    if tokenized_texts:
                        text = tokenized_texts[0]
                        new_field = f"{field}_es.tokenized_text"
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
                info_logger.info(f"Progress on applying analyzers for worker with id: {worker.pk} at {counter} out of {progress.n_total} documents!")
            elif counter == progress.n_total:
                info_logger.info(f"Finished applying analyzers for worker with id: {worker.pk} at {counter}/{progress.n_total} documents!")
