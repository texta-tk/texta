import json
import logging
from typing import List

import jwt
import requests
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from rest_framework import status, views
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from toolkit.settings import ERROR_LOGGER, INFO_LOGGER, UAA_CLIENT_ID, UAA_CLIENT_SECRET, UAA_FRONT_REDIRECT_URL, UAA_REDIRECT_URI, UAA_SUPERUSER_SCOPE, UAA_TEXTA_SCOPE_PREFIX, UAA_URL, USE_UAA


HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
}

REQUESTS_TIMEOUT_IN_SECONDS = 10


class UAAView(views.APIView):
    # Remove authentication classes to not get a 401 error on an expired token
    # See https://github.com/encode/django-rest-framework/issues/2383
    authentication_classes = []
    permission_classes = [AllowAny]


    def _decode_jit_token(self, jit_token):
        try:
            # Decode the jwt id_token
            decoded_id_token = jwt.decode(jit_token, verify=False)
            # Get the email and username from the decoded data
            user = {"user_id": decoded_id_token["user_id"], 'email': decoded_id_token['email'], 'username': decoded_id_token['user_name'], 'scope': decoded_id_token['scope']}
            return user
        except KeyError as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            return Response(f'The id_token is missing the key: {e}', status=status.HTTP_400_BAD_REQUEST)


    def _get_access_token(self, code: str):
        body = {
            'client_id': UAA_CLIENT_ID,
            'client_secret': UAA_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'token_format': 'opaque',
            'redirect_uri': UAA_REDIRECT_URI
        }
        token_url = f'{UAA_URL}/oauth/token'
        # Make a request to the oauth/token endpoint to retrieve the access_token and user info
        response = requests.post(token_url, headers=HEADERS, data=body, timeout=REQUESTS_TIMEOUT_IN_SECONDS)
        if response.ok:
            return response.json(), response.status_code
        else:
            logging.getLogger(ERROR_LOGGER).error(response.content)
            if "invalid_grant" in response.text:
                raise APIException("Invalid authorization code!", code=status.HTTP_400_BAD_REQUEST)

            raise APIException("Could not fetch the UAA access token!", code=response.status_code)


    @staticmethod
    def _update_user_and_profile(user_profile: dict, scope: List[str], token: str, user_id: str, request):
        # Get or create the user
        username = user_profile.get("user_name", "")
        email = user_profile.get("email", "")
        first_name = user_profile.get("given_name", "")
        last_name = user_profile.get("family_name", "")

        user, is_created = User.objects.get_or_create(username=username)
        user.profile.uaa_account_id = user_id
        user.profile.is_uaa_account = True

        if first_name: user.profile.first_name = first_name
        if last_name: user.profile.last_name = last_name
        if scope: user.profile.scopes = json.dumps(scope, ensure_ascii=False)
        if email: user.email = email

        if UAA_SUPERUSER_SCOPE in scope:
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False

        user.profile.save()
        user.save()

        # Delete existing once since we can't change it because the key
        # is also the primary key.
        Token.objects.filter(user=user).delete()
        Token.objects.create(user=user, key=token)
        return user


    # TODO Rethink on whether this is the best approach for this.
    def sign_in_with_user(self, user, request, scopes: List[str]):
        login(request, user)


    @staticmethod
    def _get_uaa_user_profile(user_id, access_token):
        response = requests.get(f"{UAA_URL}/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=REQUESTS_TIMEOUT_IN_SECONDS)
        if response.ok:
            return response.json()
        else:
            raise ValidationError("Could not fetch user details from UAA, is your token still valid!?")


    def _validate_toolkit_access_scope(self, scopes: str):
        """
        Users without the TEXTA prefix in their scopes are not permitted access into Toolkit.
        """
        if UAA_TEXTA_SCOPE_PREFIX not in scopes:
            raise AuthenticationFailed("Users UAA scopes do not contain access for TEXTA Toolkit!'")


    def get(self, request):
        """
        Endpoint used by the UAA login redirect_uri callback.
        Gets the access/refresh tokens for the user, and redirects them back to the frontend.
        """
        if not USE_UAA:
            logging.getLogger(INFO_LOGGER).info(f"Tried to access UAAView, but UAA is disabled as the value of USE_UAA is {USE_UAA}")
            return Response('Authentication with UAA is not enabled.', status=status.HTTP_400_BAD_REQUEST)

        code = request.query_params.get('code', None)
        if code:
            resp, status_code = self._get_access_token(code)

            # get response json
            access_token = resp['access_token']
            refresh_token = resp['refresh_token']

            jit_user_info = self._decode_jit_token(resp['id_token'])
            scope = resp['scope']

            self._validate_toolkit_access_scope(scope)

            user_id = jit_user_info['user_id']
            uaa_user_profile = UAAView._get_uaa_user_profile(user_id, access_token)

            user = UAAView._update_user_and_profile(uaa_user_profile, scope, access_token, user_id, request)
            self.sign_in_with_user(user, request, scope)
            return HttpResponseRedirect(redirect_to=f'{UAA_FRONT_REDIRECT_URL}/uaa/?access_token={access_token}&refresh_token={refresh_token}')

        else:
            logging.getLogger(INFO_LOGGER).info(f"UAAView access code asserted as False! code: {code}; request.query_params: {request.query_params}")
            # Send back the query params, as they might contain the error from UAA
            return Response({'invalid_parameters': request.query_params}, status=status.HTTP_400_BAD_REQUEST)


class RefreshUAATokenView(views.APIView):
    # Remove authentication classes to not get a 401 error on an expired token
    # See https://github.com/encode/django-rest-framework/issues/2383
    authentication_classes = []
    permission_classes = [AllowAny]


    def post(self, request):
        """OAuth 2.0 Endpoint for refreshing the access_token using refresh_token."""
        if not USE_UAA:
            logging.getLogger(INFO_LOGGER).info(f"Tried to access RefreshUAATokenView, but UAA is disabled as the value of USE_UAA is {USE_UAA}")
            return Response('Authentication with UAA is not enabled.', status=status.HTTP_400_BAD_REQUEST)
        # get & check refresh token
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response({'refresh_token': 'Parameter refresh_token missing!'}, status=status.HTTP_400_BAD_REQUEST)
        # try to refresh token
        resp = RefreshUAATokenView._refresh(refresh_token)
        # check if got 200
        if resp.status_code != 200:
            logging.getLogger(INFO_LOGGER).info(f"UAAView _get_access_token returned status {resp.status_code}!")
            return Response(f"UAAView _get_access_token returned status {resp.status_code}!", status=status.HTTP_400_BAD_REQUEST)
        return Response(resp.json(), status=status.HTTP_200_OK)


    @staticmethod
    def _refresh(refresh_token):
        body = {
            'client_id': UAA_CLIENT_ID,
            'client_secret': UAA_CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'token_format': 'opaque',
            'refresh_token': refresh_token
        }
        # Make a request to the OAuth /token endpoint to refresh the token
        return requests.post(f'{UAA_URL}/oauth/token', headers=HEADERS, data=body, timeout=REQUESTS_TIMEOUT_IN_SECONDS)
