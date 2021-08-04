import requests
import logging

from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.utils.translation import gettext_lazy as _

from rest_framework import authentication
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header
from toolkit.settings import UAA_URL
from toolkit.settings import INFO_LOGGER


class UaaAuthentication(authentication.BaseAuthentication):
    """
    Simple OAuth2 bearer token based authentication.
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Bearer ".  For example:
        Authorization: Bearer 616ae37085fb448ea79dd74d6c3013be
    """

    keyword = 'Bearer'


    # TODO Revisit this place on how to handle logouts from UAA and TK side.
    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = _('Invalid bearer header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid bearer header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        # Validate if token has expired
        username, email, resp_json = self._validate_token(auth[1].decode(), request)
        try:
            user = User.objects.get(username=username, email=email)
            return (user, None)

        except User.DoesNotExist:
            logging.getLogger(INFO_LOGGER).info(f"UaaAuthentication didn't find a matching user (OAuth tokens possibly expired) - username: {username} | email: {email} | resp_json: {resp_json}")
            raise exceptions.AuthenticationFailed(resp_json)


    def _validate_token(self, bearer_token: str, request):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Authorization': f'Bearer {bearer_token}'
        }

        # Make a request to the /userinfo endpoint to check token validity and retrieve user info
        resp = requests.get(f'{UAA_URL}/userinfo', headers=headers)
        resp_json = resp.json()

        # If the req was successful, return the user data, otherwise just return nothing
        if resp.status_code == 200:
            return resp_json['user_name'], resp_json['email'], resp_json

        return None, None, resp_json


    def authenticate_header(self, request):
        '''
        Override the authenticate_header method to change the status code of the failed resp to 401 instead of 403
        '''
        return self.keyword
