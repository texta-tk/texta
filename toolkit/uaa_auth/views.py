import json
import logging
from typing import List

import jwt
import requests
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import status, views
from rest_framework.exceptions import APIException, AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from toolkit.settings import ERROR_LOGGER, INFO_LOGGER, UAA_CLIENT_ID, UAA_CLIENT_SECRET, UAA_FRONT_REDIRECT_URL, UAA_OAUTH_TOKEN_URI, UAA_REDIRECT_URI, UAA_SUPERUSER_SCOPE, UAA_TEXTA_SCOPE_PREFIX, UAA_USERINFO_URI, USE_UAA


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
        token_url = UAA_OAUTH_TOKEN_URI
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
    def _update_user_and_profile(user_profile: dict, scope: str, token: str, request):
        # Get or create the user
        username = user_profile.get("user_name", "")
        email = user_profile.get("email", "")
        first_name = user_profile.get("given_name", "")
        last_name = user_profile.get("family_name", "")

        scope = scope.split(" ")

        user, is_created = User.objects.get_or_create(username=username)
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

        return user


    # Initially this place was used to start a session for TK so that the
    # Browsable API would also be usable but logout had a trouble of clearing said session
    # which created a mess where on a new login the still existing session was used to return the
    # previous user instead... now I just update the login timestamp manually.
    def sign_in_with_user(self, user: User, request, scopes: List[str]):
        now = timezone.now()
        user.last_login = now
        user.save()


    @staticmethod
    def _get_uaa_user_profile(access_token):
        response = requests.get(UAA_USERINFO_URI, headers={"Authorization": f"Bearer {access_token}"}, timeout=REQUESTS_TIMEOUT_IN_SECONDS)
        if response.ok:
            return response.json()
        else:
            raise ValidationError("Could not fetch user details from UAA, is your token still valid!?")


    def _validate_toolkit_access_scope(self, scopes: str):
        """
        Users without the TEXTA prefix in their scopes are not permitted access into Toolkit.
        """
        if UAA_TEXTA_SCOPE_PREFIX not in scopes and UAA_SUPERUSER_SCOPE not in scopes:
            raise AuthenticationFailed(f"Users UAA scopes '{scopes}' do not contain access for TEXTA Toolkit (match: {UAA_TEXTA_SCOPE_PREFIX}.* or {UAA_SUPERUSER_SCOPE})!")


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

            scope = resp['scope']

            self._validate_toolkit_access_scope(scope)

            uaa_user_profile = UAAView._get_uaa_user_profile(access_token)

            user = UAAView._update_user_and_profile(uaa_user_profile, scope, access_token, request)
            self.sign_in_with_user(user, request, scope)
            return HttpResponseRedirect(redirect_to=f'{UAA_FRONT_REDIRECT_URL}?access_token={access_token}&refresh_token={refresh_token}')

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
            logging.getLogger(ERROR_LOGGER).info(f"UAAView _get_access_token returned status {resp.status_code}!")
            if "invalid_token" in resp.text:
                logout(request)
            raise ValidationError(f"UAAView _get_access_token returned status {resp.status_code}!")

        json_resp = resp.json()

        # Refresh the scopes just in case with the contents of the refresh view.
        # scopes = json_resp.get("scope", "")
        # RefreshUAATokenView._update_user_scope(scopes, request.user)

        return Response(json_resp, status=status.HTTP_200_OK)


    @staticmethod
    def _update_user_scope(scopes: str, user: User):
        if UAA_SUPERUSER_SCOPE in scopes:
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False

        user.profile.scopes = scopes

        user.profile.save()
        user.save()


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
        return requests.post(UAA_OAUTH_TOKEN_URI, headers=HEADERS, data=body, timeout=REQUESTS_TIMEOUT_IN_SECONDS)
