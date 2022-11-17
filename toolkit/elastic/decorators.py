import logging
from functools import wraps

import elasticsearch
from rest_framework.exceptions import APIException
from texta_elastic.exceptions import ElasticsearchError, NotFoundError

from toolkit.elastic.exceptions import ElasticAuthenticationException, ElasticAuthorizationException, ElasticIndexNotFoundException, ElasticTimeoutException, \
    ElasticTransportException
from toolkit.settings import ERROR_LOGGER


def elastic_connection(func):
    """
    Decorator for wrapping Elasticsearch functions that are used in views,
    to return a properly formatted error message during connection issues
    instead of the typical HTTP 500 one.
    """

    @wraps(func)  # wraps is needed to use this decorator along with the extra action decorator
    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except elasticsearch.exceptions.NotFoundError as e:
            logging.getLogger(ERROR_LOGGER).error(e.info)
            raise ElasticIndexNotFoundException(f"Index lookup failed")

        except elasticsearch.exceptions.AuthorizationException as e:
            logging.getLogger(ERROR_LOGGER).warning(e.info)
            error = [error["reason"] for error in e.info["error"]["root_cause"]]
            raise ElasticAuthorizationException(f"Not authorized to access resource: {str(error)}")

        except elasticsearch.exceptions.AuthenticationException as e:
            logging.getLogger(ERROR_LOGGER).warning(e.info)
            raise ElasticAuthenticationException(f"Not authorized to access resource: {e.info}")

        except elasticsearch.exceptions.TransportError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTransportException(f"Transport to Elasticsearch failed with error: {e.error}")

        except elasticsearch.exceptions.ConnectionTimeout as e:
            logging.getLogger(ERROR_LOGGER).error(e.info)
            raise ElasticTimeoutException(f"Connection to Elasticsearch timed out!")

        except NotFoundError as e:
            raise APIException("Could not access requested resource.")

    return func_wrapper


def elastic_view(func):
    """
    After the Elastic functions got sent to their library, the previous one isn't
    functional anymore, this is for putting into views that use Elasticsearch functionality
    to throw APIExceptions on Elasticsearch related errors.
    """

    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except ElasticsearchError as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException("Could not handle the query you sent!")

        except NotFoundError as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException("Could not connect to Elasticsearch, do you have the right URL set?")

    return func_wrapper
