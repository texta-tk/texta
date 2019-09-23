import logging

import requests
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from texta.settings import ERROR_LOGGER, STATIC_URL
from django.db.utils import OperationalError


class ExceptionHandlerMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, requests.exceptions.ConnectionError):
            logging.getLogger(ERROR_LOGGER).exception(exception)
            messages.error(request, "Could not connect to resource: {}. Please check if all the resources (Elasticsearch) are available!".format(exception.request.url))
            template_data = {'STATIC_URL': STATIC_URL, 'allowed_datasets': None, 'language_models': None}
            return redirect("/", context=template_data)

        if isinstance(exception, OperationalError):
            logging.getLogger(ERROR_LOGGER).exception(exception)
            messages.error(request, "Error, please refresh the page!".format(exception))
            template_data = {'STATIC_URL': STATIC_URL, 'allowed_datasets': None, 'language_models': None}
            return redirect("/", context=template_data)

        else:
            logging.getLogger(ERROR_LOGGER).exception(exception)
            messages.error(request, "Error, please try again or contact the developers: {}!".format(exception))
            template_data = {'STATIC_URL': STATIC_URL, 'allowed_datasets': None, 'language_models': None}
            return redirect("/", context=template_data)
