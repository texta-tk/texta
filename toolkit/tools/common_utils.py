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


class DisableCSRFMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)
        return response
