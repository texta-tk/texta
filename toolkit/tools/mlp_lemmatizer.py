from toolkit.settings import MLP_URL

from urllib.parse import urljoin
import requests

class MLPLemmatizer:
    
    def __init__(self):
        self.mlp_url = urljoin(MLP_URL, 'mlp')
        self.status, self.version = self._check_connection()


    def _check_connection(self):
        """
        Checks MLP connection and major MLP version (2, 3).
        :return: bool, int
        """
        major_mlp_version = 0
        try:
            response = requests.get(MLP_URL)
            if response.status_code == 200:
                response_json = response.json()
                if "version" in response_json:
                    # this is likely version 2.x
                    major_mlp_version = self._parse_major_version(response_json)
                elif "health" in response_json:
                    # this is likely version 3.x or later
                    health_response_json = requests.get(response_json["health"])
                    if "version" in health_response_json:
                        major_mlp_version = self._parse_major_version(health_response_json)
                return True, major_mlp_version
            return False, major_mlp_version
        except:
            return False, major_mlp_version


    @staticmethod
    def _parse_major_version(response_json):
        """
        Parses major version number of MLP from health response.
        :return: int
        """
        return int(response_json["version"].split('.')[0])


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
            # if lemmatization fails, return empty string
            # TODO: log the response if lemmatization fails
            return ""
