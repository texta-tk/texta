from typing import List

from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.data_sample import ES6_SNOWBALL_MAPPING, ES7_SNOWBALL_MAPPING


LABEL_DISTRIBUTION = (
    ("random", "random"),
    ("original", "original"),
    ("equal", "equal"),
    ("custom", "custom")
)


def get_cluster_specific_languages() -> List[str]:
    ec = ElasticCore()
    first, second, third = ec.get_version()
    es6_languages = [value for key, value in ES6_SNOWBALL_MAPPING.items()]
    es7_languages = []
    if first == 7:
        es7_languages = [value for key, value in ES7_SNOWBALL_MAPPING.items()]
    return es6_languages + es7_languages


def get_snowball_choices():
    choices = [(None, None)]
    languages = get_cluster_specific_languages()
    for lang in languages:
        choices.append((lang, lang))

    return choices
