import logging

import elasticsearch

from toolkit.elastic.exceptions import ElasticAuthenticationException, ElasticAuthorizationException, ElasticIndexNotFoundException, ElasticTimeoutException, ElasticTransportException
from toolkit.settings import ERROR_LOGGER


def elastic_connection(func):
    """
    Decorator for wrapping Elasticsearch functions that are used in views,
    to return a properly formatted error message during connection issues
    instead of the typical HTTP 500 one.
    """


    def func_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except elasticsearch.exceptions.NotFoundError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticIndexNotFoundException(f"Index lookup failed")

        except elasticsearch.exceptions.AuthorizationException as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            error = [error["reason"] for error in e.info["error"]["root_cause"]]
            raise ElasticAuthorizationException(f"Not authorized to access resource: {str(error)}")

        except elasticsearch.exceptions.AuthenticationException as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticAuthenticationException(f"Not authorized to access resource: {e.info}")

        except elasticsearch.exceptions.TransportError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTransportException(f"Transport to Elasticsearch failed with error: {e.error}")

        except elasticsearch.exceptions.ConnectionTimeout as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTimeoutException(f"Connection to Elasticsearch timed out!")


    return func_wrapper
