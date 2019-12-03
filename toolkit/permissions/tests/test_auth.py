from django.urls import include, path, reverse
from django.contrib.auth.models import User

from rest_framework.test import APITestCase, URLPatternsTestCase
from rest_framework import status

from toolkit.tools.utils_for_tests import create_test_user, print_output


class AuthTests(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path('rest-auth/', include('rest_auth.urls')),
        path('rest-auth/registration/', include('rest_auth.registration.urls'))
    ]


    def setUp(self):
        self.test_user = create_test_user()


    def test_create_account(self):
        """
        Ensure we can register.
        """
        url = '/rest-auth/registration/'

        response = self.client.post(url, {
            'username': 'unitTestUser',
            'email': 'unitTestUser@mail.com',
            'password1': 'safepassword123',
            'password2': 'safepassword123',
        })

        print_output("creating API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


    def test_login(self):
        """
        Ensure we can log in.
        """
        url = '/rest-auth/login/'

        response = self.client.post(url, {
            'username': 'tester',
            'password': 'password',
        })

        print_output("Login to API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def test_logout(self):
        """
        Ensure we can log out.
        """
        url = '/rest-auth/logout/'

        self.client.force_authenticate(self.test_user)
        response = self.client.post(url)

        print_output("Log out of API account", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
