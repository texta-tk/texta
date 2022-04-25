from django.urls import include, path

from rest_framework.test import APITestCase, URLPatternsTestCase
from rest_framework import status

from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_VERSION_PREFIX


class AuthTests(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path(f'{TEST_VERSION_PREFIX[1:]}/rest-auth/', include('dj_rest_auth.urls')),
        path(f'{TEST_VERSION_PREFIX[1:]}/rest-auth/registration/', include('dj_rest_auth.registration.urls'))
    ]

    def setUp(self):
        self.test_user = create_test_user()

    def test_run(self):
        self.create_account(),
        self.login(),
        self.logout(),
        self.change_password(),

    def create_account(self):
        """
        Ensure we can register.
        """
        url = f'{TEST_VERSION_PREFIX}/rest-auth/registration/'

        response = self.client.post(url, {
            'username': 'unitTestUser',
            'email': 'unitTestUser@mail.com',
            'password1': 'safepassword123',
            'password2': 'safepassword123',
        })

        print_output("creating API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def login(self):
        """
        Ensure we can log in.
        """
        url = f'{TEST_VERSION_PREFIX}/rest-auth/login/'

        response = self.client.post(url, {
            'username': 'tester',
            'password': 'password',
        })

        print_output("Login to API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def logout(self):
        """
        Ensure we can log out.
        """
        url = f'{TEST_VERSION_PREFIX}/rest-auth/logout/'

        self.client.force_authenticate(self.test_user)
        response = self.client.post(url)

        print_output("Log out of API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def change_password(self):
        """
        Ensure we can change password
        """
        url = f'{TEST_VERSION_PREFIX}/rest-auth/password/change/'
        self.client.login(username='tester', password='password')

        payload = {
            "new_password1": "safepassword123",
            "new_password2": "safepassword123"
        }

        response = self.client.post(url, payload)
        print_output("Change password response", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # TODO? reset password
