def find_key_recursivly(key: str, dictionary: dict):
    """
    Function that returns all instances of the given keys value inside a dictionary.
    Searches recursively through the dictionary and yields the results.
    :param key: String of the key whose values are being searched.
    :param dictionary: Target dictionary to traverse.
    :return:
    """
    for k, v in dictionary.items():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in find_key_recursivly(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                if isinstance(d, dict):
                    for result in find_key_recursivly(key, d):
                        yield result
