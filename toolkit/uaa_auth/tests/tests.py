import unittest
from urllib.parse import parse_qs, urlparse

import bs4
import json
import requests
from rest_framework.test import APILiveServerTestCase

from toolkit.settings import UAA_CLIENT_ID, UAA_REDIRECT_URI, UAA_URL, USE_UAA, UAA_CLIENT_SECRET
from toolkit.test_settings import TEST_LIVE_SERVER_PORT, TEST_UAA_PASSWORD, TEST_UAA_USERNAME, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


# Use the APILiveServerTestCase as we need the server to run for the callback from UAA
class UAATests(APILiveServerTestCase):
    port = TEST_LIVE_SERVER_PORT

    def setUp(self):
        self.url = f'{TEST_VERSION_PREFIX}/uaa'
        self.test1_user = "test1"  # Used for test1 user id
        self.test2_user = "test2"  # Used for test2 user id
        self.test3_user = "test3"  # Used for test3 user id
        # Create a normal User
        self.user = create_test_user(name='normaluser', password='pw')
        self.create_users()
        self.create_groups()
        self.create_project1()
        self.create_project2()
        self.create_project3()

    @unittest.skipUnless(USE_UAA, 'Skipping UAA test because USE_UAA is set to False')
    def test(self):
        self.run_callback_incorrect_params()
        self.run_callback_invalid_code()
        self.run_login_with_refresh_and_access_token_success()
        self.run_auth_incorrect_header()
        self.run_auth_invalid_token()
        self.run_refresh_token_incorrect_params()
        self.run_refresh_token_invalid_token()
        self.run_user_is_not_superuser_without_admin_group()
        self.run_user_in_scopes_has_access_to_project_where_user_is_not_listed()
        self.run_that_user_with_projadmin_scope_can_do_proj_admin_procedures()
        self.run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures()
        self.run_that_normal_user_in_scope_does_not_have_admin_access()
        self.run_that_normally_added_user_still_has_access_even_if_not_in_set_scope()

    def create_users(self):
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.admin uaa.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_create_users:csrf_token", csrf_token)
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
            print_output("run_create_users_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_create_users:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_create_users:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            headers = {
                "Accept": "application/json",
                "content-type": "application/json",
                "Authorization": f'Bearer {query_params["access_token"][0]}'
            }
            # Create test1 user
            body = {
                "userName": self.test1_user,
                "name": {
                    "formatted": "given name family name",
                    "familyName": "user",
                    "givenName": "test1"
                },
                "emails": [{
                    "value": "test1@test.org",
                    "primary": True
                }],
                "active": True,
                "verified": True,
                "origin": "",
                "password": "test1"
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Users', headers=headers, data=json_data)
            self.test1_user = json.loads(create_resp.content)
            print_output("run_create_test1_user:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)
            # Create test2 user
            body = {
                "userName": self.test2_user,
                "name": {
                    "formatted": "given name family name",
                    "familyName": "user",
                    "givenName": "test2"
                },
                "emails": [{
                    "value": "test2@test.org",
                    "primary": True
                }],
                "active": True,
                "verified": True,
                "origin": "",
                "password": "test2"
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Users', headers=headers, data=json_data)
            self.test2_user = json.loads(create_resp.content)
            print_output("run_create_test2_user:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)
            # Create test3 user
            body = {
                "userName": self.test3_user,
                "name": {
                    "formatted": "given name family name",
                    "familyName": "user",
                    "givenName": "test3"
                },
                "emails": [{
                    "value": "test3@test.org",
                    "primary": True
                }],
                "active": True,
                "verified": True,
                "origin": "",
                "password": "test3"
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Users', headers=headers, data=json_data)
            self.test3_user = json.loads(create_resp.content)
            print_output("run_create_test3_user:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)

    def create_groups(self):
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.admin uaa.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_create_groups:csrf_token", csrf_token)
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
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_create_groups:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_create_groups:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            headers = {
                "Accept": "application/json",
                "content-type": "application/json",
                "Authorization": f'Bearer {query_params["access_token"][0]}'
            }
            # Create texta.ou group and add users to group
            body = {
                "displayName": "texta.ou",
                "members": [{
                    "type": "USER",
                    "value": self.test1_user["id"]
                },
                    {
                        "type": "USER",
                        "value": self.test2_user["id"]
                    },
                    {
                        "type": "USER",
                        "value": self.test3_user["id"]
                    }]
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Groups', headers=headers, data=json_data)
            print_output("run_create_texta_ou_user_group:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)
            # Create texta.project_admin group and add users to group
            body = {
                "displayName": "texta.project_admin",
                "members": [{
                    "type": "USER",
                    "value": self.test1_user["id"]
                },
                    {
                        "type": "USER",
                        "value": self.test2_user["id"]
                    }]
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Groups', headers=headers, data=json_data)
            print_output("run_create_texta_project_admin_user_group:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)
            # Create texta.admin group and add users to group
            body = {
                "displayName": "texta.admin",
                "members": [{
                    "type": "USER",
                    "value": self.test1_user["id"]
                }]
            }
            json_data = json.dumps(body)
            create_resp = requests.post(f'{UAA_URL}/Groups', headers=headers, data=json_data)
            print_output("run_create_texta_project_admin_user_group:resp", create_resp)
            self.assertEqual(201, create_resp.status_code)

    def create_project1(self):
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("create_projects:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test3&password=test3&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_create_projects_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("create_projects:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("create_projects:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("create_projects:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # create user projects
            payload = {
                "title": "project1",
                "administrators_write": ["test3"],
                "users_write": ["test3"],
                "indices_write": []
            }
            user_resp = self.client.post(f'{TEST_VERSION_PREFIX}/projects/', payload, format='json')
            print_output("create_projects:projects",
                         user_resp.data)
            print_output("create_projects:status_code", user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()
            self.assertEqual(201, user_resp.status_code)

    def create_project2(self):
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.ou texta.project_admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("create_projects:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test2&password=test2&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_create_projects_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("create_projects:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("create_projects:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("create_projects:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # create user projects
            payload = {
                "title": "project2",
                "administrators_write": ["test2"],
                "users_write": ["test2", "test3"],
                "indices_write": []
            }
            user_resp = self.client.post(f'{TEST_VERSION_PREFIX}/projects/', payload, format='json')
            print_output("create_projects:projects",
                         user_resp.data)
            print_output("create_projects:status_code", user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()
            self.assertEqual(201, user_resp.status_code)

    def create_project3(self):
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.ou texta.admin texta.project_admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("create_projects:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test1&password=test1&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_create_projects_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("create_projects:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("create_projects:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("create_projects:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # create user projects
            payload = {
                "title": "project3",
                "administrators_write": ["test1"],
                "users_write": ["test1", "test2", "test3"],
                "indices_write": []
            }
            user_resp = self.client.post(f'{TEST_VERSION_PREFIX}/projects/', payload, format='json')
            print_output("create_projects:projects",
                         user_resp.data)
            print_output("create_projects:status_code", user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()
            self.assertEqual(201, user_resp.status_code)

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
        self.assertEqual(500, response.status_code)

    def run_login_with_refresh_and_access_token_success(self):
        '''
        Test if the redirect_uri callback gives the correct response on a valid code,
        if the refresh-token endpoint works with the received refresh_token, as well as
        whether or not the UaaAuthentication works with the correct access_token.
        '''

        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.admin uaa.admin&redirect_uri={encoded_redirect_uri}'

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
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
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
            refresh_resp = self.client.post(f'{self.url}/refresh-token/',
                                            {'refresh_token': query_params['refresh_token'][0]}, format='json')

            print_output("run_callback_and_refresh_and_access_token_success:refresh_resp.data", refresh_resp.data)
            print_output("run_callback_and_refresh_and_access_token_success:refresh_resp.data",
                         refresh_resp.status_code)
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
        # self.assertTrue('error_description' in response.data)
        # Check if it gives a specific response
        # self.assertTrue('invalid_token' in response.data['error'])

    def run_user_is_not_superuser_without_admin_group(self):
        '''
        Test if the user is not superuser since texta.admin is not in scope
        '''
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=texta.admin openid texta.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_user_is_not_superuser_without_admin_group:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test2&password=test2&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_user_is_not_superuser_without_admin_group:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_user_is_not_superuser_without_admin_group:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("run_user_is_not_superuser_without_admin_group:auth_resp.data", auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # Get user profile
            user_resp = self.client.get(f'{TEST_VERSION_PREFIX}/rest-auth/user/', format='json')
            print_output("run_user_is_not_superuser_without_admin_group:user",
                         user_resp.data)
            # Check that user is not superuser
            self.assertEqual(False, user_resp.data['is_superuser'])
            # Stop including any credentials
            self.client.credentials()

    def run_user_in_scopes_has_access_to_project_where_user_is_not_listed(self):
        '''
        Test if the user in scope has access to project where user is not listed
        '''
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=texta.admin openid texta.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test2&password=test2&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # Get user projects
            user_resp = self.client.get(f'{TEST_VERSION_PREFIX}/projects/1/', format='json')
            print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:data",
                         user_resp.data)
            print_output("run_user_in_scopes_has_access_to_project_where_user_is_not_listed:status_code",
                         user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()
            self.assertEqual(404, user_resp.status_code)

    def run_that_user_with_projadmin_scope_can_do_proj_admin_procedures(self):
        '''
        Test if user with texta.project_admin scope can do project admin procedures
        '''
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=texta.admin openid texta.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:csrf_token",
                     csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test1&password=test1&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:query_params",
                         query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # Get user projects
            user_resp = self.client.patch(f'{TEST_VERSION_PREFIX}/projects/1/', {
                "title": "test_project",
                "administrators_write": ["test1"],
                "users_write": ["test1"],
                "indices_write": []
            }, format='json')
            print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:data",
                         user_resp.data)
            print_output("run_that_user_with_projadmin_scope_can_do_proj_admin_procedures:projects",
                         user_resp.status_code)
            # Check that user is not superuser
            self.assertEqual(200, user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()

    def run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures(self):
        '''
        Test that user without project_admin scope cannot do project admin procedures
        '''
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.ou&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:csrf_token",
                     csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test3&password=test3&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_callback_login_resp", login_resp)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:query_params",
                         query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:auth_resp.data",
                         auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # Get user projects
            user_resp = self.client.patch(f'{TEST_VERSION_PREFIX}/projects/2/', {
                "title": "test_project_updated",
                "administrators_write": ["test1"],
                "users_write": ["test1", "test3"],
                "indices_write": []
            }, format='json')
            print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:status_code",
                         user_resp.data)
            print_output("run_that_user_without_projadmin_scope_cant_do_proj_admin_procedures:status_code",
                         user_resp.status_code)
            # Check that user is not superuser
            self.assertEqual(403, user_resp.status_code)
            # Stop including any credentials
            self.client.credentials()

    def run_that_normal_user_in_scope_does_not_have_admin_access(self):
        '''
        Test that normal user in scope does not have admin access
        '''
        # Encode the redirect_uri
        encoded_redirect_uri = requests.utils.quote(UAA_REDIRECT_URI)
        uaa_login_url = f'{UAA_URL}/oauth/authorize?response_type=code&client_id={UAA_CLIENT_ID}&scope=openid texta.admin&redirect_uri={encoded_redirect_uri}'

        # Get the csrf token from the login page HTML
        html_resp = requests.get(uaa_login_url)
        soup = bs4.BeautifulSoup(html_resp.text, 'lxml')
        csrf_token = soup.select_one('[name="X-Uaa-Csrf"]')['value']
        print_output("test_user_is_no_longer_superuser_after_admin_group_removal:csrf_token", csrf_token)
        self.assertTrue(csrf_token)

        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'X-Uaa-Csrf={csrf_token}'
        }

        # The form_redirect_uri will be the encoded version of the uaa_login_uri
        body = f'X-Uaa-Csrf={csrf_token}&username=test3&password=test3&form_redirect_uri={requests.utils.quote(uaa_login_url)}'

        try:
            # POST to the login.do endpoint to trigger the redirect_uri callback in the view.
            login_resp = requests.post(f'{UAA_URL}/login.do', headers=headers, data=body)
            print_output("run_callback_login_resp_for_normal_user", login_resp.content)
        except requests.exceptions.ConnectionError as e:
            # The callback view redirects the user back to the frontend,
            # since frontend is not running during tests, it will throw a ConnectionError.
            # Check the URL which gave the ConnectionError and verify that it has the access and refresh tokens as qparams
            url = e.request.url
            print_output("test_user_is_no_longer_superuser_after_admin_group_removal:url", url)

            query_params = parse_qs(urlparse(url).query)
            print_output("test_user_is_no_longer_superuser_after_admin_group_removal:query_params", query_params)
            self.assertTrue('access_token' in query_params)
            self.assertTrue('refresh_token' in query_params)

            # Validate if the UaaAuthentication gives the correct response on a correct token
            # Auth the root url
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {query_params["access_token"][0]}')
            auth_resp = self.client.get(f'{TEST_VERSION_PREFIX}/', format='json')
            print_output("test_user_is_no_longer_superuser_after_admin_group_removal:auth_resp.data", auth_resp.data)
            # Check if the UaaAuthentication returned 200
            self.assertEqual(200, auth_resp.status_code)
            # Get user profile
            user_resp = self.client.get(f'{TEST_VERSION_PREFIX}/rest-auth/user/', format='json')
            print_output("test_user_is_no_longer_superuser_after_admin_group_removal:user",
                         user_resp.data)
            # Check that user is not superuser
            self.assertEqual(False, user_resp.data['is_superuser'])
            # Stop including any credentials
            self.client.credentials()

    def run_that_normally_added_user_still_has_access_even_if_not_in_set_scope(self):
        '''
        Test if normal user can login
        '''
        response = self.client.login(username="normaluser", password="pw")
        print_output("normal user login", response)
        self.assertTrue(response)
