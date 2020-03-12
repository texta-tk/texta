from toolkit.elastic.exceptions import InvalidIndexNameException


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
