from itertools import zip_longest


def grouper(n, iterable, fillvalue=None):
    """
    Iterating trough an iterator/generator with chunks
    of size n.
    """
    container = []

    args = [iter(iterable)] * n
    chunks = zip_longest(fillvalue=fillvalue, *args)
    for chunk in chunks:
        chunk = [chunk for chunk in chunk if chunk is not None]
        container.append(chunk)

    return container[0]
