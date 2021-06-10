import requests
import logging
import jwt

from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_auth import app_settings

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.settings import UAA_CLIENT_ID, UAA_CLIENT_SECRET, UAA_URL, UAA_FRONT_REDIRECT_URL, UAA_REDIRECT_URI, USE_UAA
from toolkit.settings import INFO_LOGGER, ERROR_LOGGER


HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
}

class UAAView(views.APIView):
    # Remove authentication classes to not get a 401 error on an expired token
    # See https://github.com/encode/django-rest-framework/issues/2383
    authentication_classes = []
    permission_classes = [AllowAny]


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
            try:
                # Decode the jwt id_token
                decoded_id_token = jwt.decode(resp_json['id_token'], verify=False)
                # Get the email and username from the decoded data
                user = { 'email': decoded_id_token['email'], 'username': decoded_id_token['user_name'] }
            except KeyError as e:
                logging.getLogger(ERROR_LOGGER).exception(e)
                return Response(f'The id_token is missing the key: {e}', status=status.HTTP_400_BAD_REQUEST)

            serializer, created_user = UAAView._auth_uaa_user(user['email'], user['username'], request)
            profile = UserProfile.filter(user=created_user).update(scope=user['scope'])
            return HttpResponseRedirect(redirect_to=f'{UAA_FRONT_REDIRECT_URL}/uaa/?access_token={access_token}&refresh_token={refresh_token}')

        else:
            logging.getLogger(INFO_LOGGER).info(f"UAAView access code asserted as False! code: {code}; request.query_params: {request.query_params}")
            # Send back the query params, as they might contain the error from UAA
            return Response({'invalid_parameters': request.query_params}, status=status.HTTP_400_BAD_REQUEST)


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


    def _auth_uaa_user(email, username, request):
        # Get or create the user
        user, created = User.objects.get_or_create(username=username, email=email)
        # Log in the user
        login(request, user)
        # Serialize the user
        serializer = UserSerializer(user, context={'request': request})
        return serializer, user


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
