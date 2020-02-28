import logging

from toolkit.exceptions import MLPNotAvailable
from toolkit.settings import MLP_URL, ERROR_LOGGER

from urllib.parse import urljoin
import requests


def check_mlp_connection(func):
    def func_wrapper(*args, **kwargs):

        try:
            response = requests.get(MLP_URL, timeout=3)
            if not response.ok: raise MLPNotAvailable()
            return func(*args, **kwargs)

        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
            logging.getLogger(ERROR_LOGGER).error(e)
            raise MLPNotAvailable()


    return func_wrapper


class MLPAnalyzer:

    def __init__(self):
        self.mlp_url = urljoin(MLP_URL, 'mlp')


    @check_mlp_connection
    def process(self, text):
        # TODO: remove unused analyzers in request for MLP 3.x
        response = requests.post(self.mlp_url, data=text.encode())

        if response.status_code == 200:
            response_json = response.json()
            return response_json
        else:
            # if processing fails, return empty dict
            # TODO: log the response if processing fails
            return {}


    @check_mlp_connection
    def lemmatize(self, text):
        response = requests.post(self.mlp_url, data=text.encode())
        if response.status_code == 200:
            response_json = response.json()
            lemmas = response_json["text"]["lemmas"]
            return lemmas
        else:
            # if lemmatization fails, return empty string
            # TODO: log the response if lemmatization fails
            return ""
