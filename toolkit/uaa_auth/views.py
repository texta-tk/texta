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
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from toolkit.settings import ERROR_LOGGER, INFO_LOGGER, UAA_CLIENT_ID, UAA_CLIENT_SECRET, UAA_FRONT_REDIRECT_URL, UAA_REDIRECT_URI, UAA_URL, USE_UAA


HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
}


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
        return requests.post(token_url, headers=HEADERS, data=body)


    @staticmethod
    def _update_user_and_profile(user_profile: dict, scope: List[str], token: str, user_id: str, request):
        # Get or create the user
        username = user_profile["userName"]
        emails = [email["value"] for email in user_profile["emails"]]
        email = emails[0] if emails else ""
        name_dict = user_profile.get("name", {})
        first_name = name_dict.get("givenName", None)
        last_name = name_dict.get("familyName", None)

        user, is_created = User.objects.get_or_create(username=username)
        user.profile.uaa_account_id = user_id
        user.profile.is_uaa_account = True

        if first_name: user.profile.first_name = first_name
        if last_name: user.profile.last_name = last_name
        if scope: user.profile.scope = json.dumps(scope, ensure_ascii=False)
        if email: user.email = email

        user.profile.save()
        user.save()

        # Delete existing once since we can't change it because the key
        # is also the primary key.
        Token.objects.filter(user=user).delete()
        Token.objects.create(user=user, key=token)
        return user


    # TODO Rethink on whether this is the best approach for this.
    def sign_in_with_user(self, user, request):
        login(request, user)


    @staticmethod
    def _get_uaa_user_profile(user_id, access_token):
        response = requests.get(f"{UAA_URL}/Users/{user_id}", headers={"Authorization": f"Bearer {access_token}"})
        if response.ok:
            return response.json()
        else:
            raise ValidationError("Could not fetch user details from UAA, is your token still valid!?")


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
            resp = self._get_access_token(code)
            # On error, send a 400 resp with the error with the json contents
            if resp.status_code != 200:
                logging.getLogger(INFO_LOGGER).info(f"UAAView _get_access_token returned status {resp.status_code}!")
                return Response(f"UAAView _get_access_token returned status {resp.status_code}!", status=status.HTTP_400_BAD_REQUEST)

            # get response json
            resp_json = resp.json()
            access_token = resp_json['access_token']
            refresh_token = resp_json['refresh_token']

            jit_user_info = self._decode_jit_token(resp_json['id_token'])
            scope = jit_user_info['scope']
            user_id = jit_user_info['user_id']

            uaa_user_profile = UAAView._get_uaa_user_profile(user_id, access_token)

            user = UAAView._update_user_and_profile(uaa_user_profile, scope, access_token, user_id, request)
            self.sign_in_with_user(user, request)
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
        return requests.post(f'{UAA_URL}/oauth/token', headers=HEADERS, data=body)
