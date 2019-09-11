import traceback
import logging
from toolkit.logging_settings import ERROR_LOGGER


class ExceptionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        print('called')
        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    def process_exception(self, request, exception):
        print('IN MIDDLEWARE!')
        
        print(exception)
        import pdb; pdb.set_trace()
        logging.getLogger(ERROR_LOGGER).error("Neurotagger views", extra={'exception': exception}, exc_info=True)
        print('IN MIDDLEWARE!')
        print(traceback, request)
        return None
