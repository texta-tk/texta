import logging
from typing import Optional

from toolkit.settings import ELASTIC_CLUSTER_VERSION, INFO_LOGGER


# https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-tokenizers.html
ELASTIC_TOKENIZERS = (
    ("keyword", "keyword"),
    ("standard", "standard"),
    ("letter", "letter"),
    ("lowercase", "lowercase"),
    ("whitespace", "whitespace"),
    ("uax_url_email", "uax_url_email"),
    ("classic", "classic"),
    ("thai", "thai")
)

DEFAULT_ELASTIC_TOKENIZER = "standard"

LABEL_DISTRIBUTION = (
    ("random", "random"),
    ("original", "original"),
    ("equal", "equal"),
    ("custom", "custom")
)

ES6_SNOWBALL_MAPPING = {
    "ca": "catalan",
    "da": "danish",
    "nl": "dutch",
    "en": "english",
    "fi": "finnish",
    "fr": "french",
    "de": "german",
    "hu": "hungarian",
    "it": "italian",
    "lt": "lithuanian",
    "no": "norwegian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "es": "spanish",
    "sv": "swedish",
    "tr": "turkish",
}

ES7_SNOWBALL_MAPPING = {"ar": "arabic", "et": "estonian"}
DEFAULT_SNOWBALL_LANGUAGE = None


def map_iso_to_snowball(iso_code: str) -> Optional[str]:
    mapping = {**ES6_SNOWBALL_MAPPING, **ES7_SNOWBALL_MAPPING}
    language = mapping.get(iso_code, None)
    return language


def get_snowball_choices():
    default_choices = [(DEFAULT_SNOWBALL_LANGUAGE, DEFAULT_SNOWBALL_LANGUAGE)]
    if ELASTIC_CLUSTER_VERSION == 7:
        languages = {**ES7_SNOWBALL_MAPPING, **ES6_SNOWBALL_MAPPING}
    elif ELASTIC_CLUSTER_VERSION == 6:
        languages = ES6_SNOWBALL_MAPPING
    else:
        # Just in case, default to the most minimal options.
        languages = ES6_SNOWBALL_MAPPING
        logging.getLogger(INFO_LOGGER).warning("Unspecified Elastic cluster version when determining Snowball options!")

    for key, value in languages.items():
        default_choices.append((value, value))

    return default_choices
