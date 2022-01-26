from toolkit.elastic.exceptions import InvalidIndexNameException, NoIndexExists
from toolkit.elastic.index.models import Index
from texta_elastic.core import ElasticCore


def parse_index_input(value) -> str:
    """
    Function to parse both list of string and list of dicts
    handling of indices.
    :param value: A singular item in the 'indices' field.
    :return: String name of a single index in a list of indices.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value["name"]
    pass

def check_for_wildcards(value: str):
    if "*" in value:
        raise InvalidIndexNameException("Wildcards are not allowed in Index operations!")


def check_for_colons(value: str):
    if ":" in value:
        raise InvalidIndexNameException("':' symbols are not allowed in Index names!")


def check_for_special_symbols(value: str):
    special_symbols = {"#", " ", "/", "\\", "*", "?", "\"", ">", "<", ",", "|"}
    for char in value:
        if char in special_symbols:
            raise InvalidIndexNameException(f"{char} is amongst the banned characters for index names!")


def check_for_banned_beginning_chars(value: str):
    first_char = value[0]
    banned_chars = ["-", "+", "_"]
    if first_char in banned_chars:
        raise InvalidIndexNameException(f"{first_char} is not allowed to be the first character of the index name!")


def check_for_upper_case(value: str):
    for char in value:
        if char.isupper():
            raise InvalidIndexNameException("Uppercase characters are not allowed!")


def check_for_existence(value):
    ec = ElasticCore()
    index = parse_index_input(value)
    in_elastic = ec.check_if_indices_exist(indices=[index])
    if in_elastic:
        # This line helps keep the database and Elastic in sync.
        index, is_created = Index.objects.get_or_create(name=index)
    else:
        # We check for a loose Index object just in case and delete them.
        Index.objects.filter(name=index).delete()
        raise NoIndexExists(f"Could not access index '{index}'")
