from toolkit.settings import MLP_URL

from urllib.parse import urljoin
import requests

class MLPLemmatizer:
    
    def __init__(self, lite=False):
        self.mlp_url = self._create_url(lite)
        self.status = self._check_connection()


    @staticmethod
    def _create_url(lite):
        """
        Creates url based on lite option.
        :return: MLP resource url as string
        """
        if lite == True:
            return urljoin(MLP_URL, 'mlp_lite')
        else:
            return urljoin(MLP_URL, 'mlp')


    @staticmethod
    def _check_connection():
        try:
            response = requests.get(MLP_URL)
            if response.status_code == 200:
                return True
            return False
        except:
            return False


    def lemmatize(self, text):
        response = requests.post(self.mlp_url, data=text.encode())
        if response.status_code == 200:
            response_json = response.json()
            text = response_json["text"]
            # this magic is required because MLP returns a dict & MLP lite returns a string
            if isinstance(text, dict):
                text = text["lemmas"]
            return text
        else:
            # if lemmatization fails, return None
            # TODO: log the response if lemmatization fails
            return None
