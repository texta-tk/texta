from django.urls import include, path, reverse
from django.contrib.auth.models import User

from rest_framework.test import APITestCase, URLPatternsTestCase
from rest_framework import status


class AuthTests(APITestCase, URLPatternsTestCase):
    urlpatterns = [
        path('rest-auth/', include('rest_auth.urls')),
        path('rest-auth/registration/', include('rest_auth.registration.urls'))
    ]


    def setUp(self):
        self.test_user = User(username='logInTester', email='my@email.com')
        self.test_user.set_password('safepass')
        self.test_user.save()


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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 1)


    def test_login(self):
        """
        Ensure we can log in.
        """
        url = '/rest-auth/login/'

        response = self.client.post(url, {
            'username': 'logInTester',
            'password': 'safepass',
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


    def test_logout(self):
        """
        Ensure we can log out.
        """
        url = '/rest-auth/logout/'

        self.client.force_authenticate(self.test_user)
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
