from urllib.parse import urlparse, parse_qs
import requests
import bs4
import unittest

from rest_framework.test import APILiveServerTestCase

from toolkit.test_settings import TEST_VERSION_PREFIX, TEST_UAA_PASSWORD, TEST_UAA_USERNAME, TEST_LIVE_SERVER_PORT
from toolkit.tools.utils_for_tests import print_output
from toolkit.settings import UAA_CLIENT_ID, UAA_REDIRECT_URI, UAA_URL, USE_UAA


# Use the APILiveServerTestCase as we need the server to run for the callback from UAA
class UAATests(APILiveServerTestCase):
    port = TEST_LIVE_SERVER_PORT

    def setUp(self):
        self.url = f'{TEST_VERSION_PREFIX}/uaa'

    @unittest.skipUnless(USE_UAA, 'Skipping UAA test because USE_UAA is set to False')
    def test(self):
        self.run_callback_incorrect_params()
        self.run_callback_invalid_code()
        self.run_callback_and_refresh_and_access_token_success()
        self.run_auth_incorrect_header()
        self.run_auth_invalid_token()
        self.run_refresh_token_incorrect_params()
        self.run_refresh_token_invalid_token()


    def run_callback_incorrect_params(self):
        '''
        Test if the redirect_uri callback gives the correct response
        on incorrect query parameters
        '''
        url = f'{self.url}/callback?notcode=someinvalidstring'
        response = self.client.get(url, format='json')
        # Check if the query parameter was returned, because UAA puts errors
        # into the query params
        self.assertTrue('invalid_parameters' in response.data)
        self.assertTrue('notcode' in response.data['invalid_parameters'])
        self.assertEqual(400, response.status_code)
        print_output("run_callback_incorrect_params", response.data)


    def run_callback_invalid_code(self):
        '''
        Test if the redirect_uri callback gives the correct response
        on an invalid code query param
        '''
        url = f'{self.url}/callback?code=someinvalidstring'
        response = self.client.get(url, format='json')
        # Check if the UAA server returned an error response through the callback view
        print_output("run_callback_invalid_code", response.data)
        self.assertEqual(400, response.status_code)



    def run_callback_and_refresh_and_access_token_success(self):
        '''
        Test if the redirect_uri callback gives the correct response on a valid code,
        if the refresh-token endpoint works with the received refresh_token, as well as
        whether or not the UaaAuthentication works with the correct access_token.
        '''

        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_callback_and_refresh_and_access_token_success:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username={TEST_UAA_USERNAME}&password={TEST_UAA_PASSWORD}&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
        except requests.exceptions.ConnectionError  as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_callback_and_refresh_and_access_token_success:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_callback_and_refresh_and_access_token_success:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            # Stop including any credentials
            self.client.credentials()
            print_output("run_callback_and_refresh_and_access_token_success:auth_resp.data", auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)

            # Validate if the refresh-token endpoint works with the correct refresh_token
            # Post to the refresh-token endpoint
            refresh_resp = self.client.post(f'{self.url}/refresh-token',
                                    {'refresh_token': query_params['refresh_token'][0]}, format='json')

            print_output("run_callback_and_refresh_and_access_token_success:refresh_resp.data", refresh_resp.data)
            print_output("run_callback_and_refresh_and_access_token_success:refresh_resp.data", refresh_resp.status_code)
            # Check if the refresh-token endpoint returned 200
            self.assertEqual(200, refresh_resp.status_code)
            # Check if a new refresh_token and access_token are attached
            self.assertTrue('refresh_token' in refresh_resp.data)
            self.assertTrue('access_token' in refresh_resp.data)


    def run_auth_incorrect_header(self):
        '''
        Test if UaaAuthentication gives the correct response on an incorrect header
        '''
        # Auth the root url
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalidcode invalidformat')
        response = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
        # Stop including any credentials
        self.client.credentials()

        print_output("run_auth_incorrect_header", response.data)
        # Check if the UaaAuthentication returned 401
        self.assertTrue('detail' in response.data)
        # Check if it gives a specific response
        self.assertTrue('Invalid bearer header' in response.data['detail'])
        self.assertEqual(401, response.status_code)


    def run_auth_invalid_token(self):
        '''
        Test if UaaAuthentication gives the correct response on an invalid/expired token
        '''
        # Auth the root url
        self.client.credentials(HTTP_AUTHORIZATION='Bearer expiredcode')
        response = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
        # Stop including any credentials
        self.client.credentials()

        print_output("run_auth_invalid_token", response.data)
        # Check if the UaaAuthentication returned 401
        self.assertTrue('error' in response.data)
        # Check if it gives a specific response
        self.assertTrue('The token expired,' in response.data['error_description'])
        self.assertEqual(401, response.status_code)


    def run_refresh_token_incorrect_params(self):
        '''
        Test if the refresh token endpoint gives the correct response on incorrect params
        '''
        # Auth the root url
        response = self.client.post(f'{self.url}/refresh-token',
                                    {'wrongparam': 'wrongvalue'}, format='json')

        print_output("run_refresh_token_invalid_params", response.data)
        # Check if the refresh-token endpoint returned 400
        self.assertTrue('refresh_token' in response.data)
        # Check if it gives a specific response
        self.assertTrue('refresh_token missing' in response.data['refresh_token'])
        self.assertEqual(400, response.status_code)


    def run_refresh_token_invalid_token(self):
        '''
        Test if the refresh token endpoint gives the correct response on an invalid/expired token
        '''
        # Auth the root url
        response = self.client.post(f'{self.url}/refresh-token',
                                    {'refresh_token': 'wrongvalue'}, format='json')

        print_output("run_refresh_token_invalid_token", response.data)
        # Check if the refresh-token endpoint returned 403
        self.assertEqual(400, response.status_code)
        #self.assertTrue('error_description' in response.data)
        # Check if it gives a specific response
        #self.assertTrue('invalid_token' in response.data['error'])
