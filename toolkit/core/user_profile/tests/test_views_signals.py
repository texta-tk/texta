from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.user_profile.models import UserProfile
from toolkit.tools.utils_for_tests import create_test_user, print_output


class UserProfileSignalsAndViewsTests(APITestCase):

    def setUp(cls):
        # Create admin user with pk 1
        cls.admin = create_test_user(name='admin', password='1234')
        cls.admin.is_superuser = True
        cls.admin.save()
        # Create a new User
        cls.user = create_test_user(name='user', password='pw')

    def test_run(self):
        self.run_profile_object()
        self.run_profile_login()
        self.assign_superuser()

    def run_profile_object(self):
        '''Test whether or not UserProfile object was created'''
        self.assertTrue(UserProfile.objects.filter(user=self.user.pk).exists())

    def run_profile_login(self):
        '''Test if the UserProfile view is working'''
        url = f'/users/{self.user.profile.id}/'
        self.client.login(username='user', password='pw')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def assign_superuser(self):

        assign_payload = {
            "is_superuser": True
        }
        deassign_payload = {
            "is_superuser": False
        }

        admin_url = f'/users/{self.admin.profile.id}/'
        user_url = f'/users/{self.user.profile.id}/'

        self.client.login(username='admin', password='1234')
        # check that user is not superuser
        print_output("User superuser status before assign", self.user.is_superuser)
        assert not self.user.is_superuser

        # can't assign original admin
        put_response = self.client.put(admin_url, assign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_403_FORBIDDEN)
        print_output("assign superuser response data", put_response.data)

        # assign superuser status to user
        put_response = self.client.put(user_url, assign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        print_output("assign superuser response data", put_response.data)

        # check that user is superuser
        print_output("User superuser status after assign", put_response.data['is_superuser'])
        assert put_response.data['is_superuser']

        # de-assign superuser
        put_response = self.client.put(user_url, deassign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        print_output("de-assign superuser response data", put_response.data)

        # check that superuser status was removed
        print_output("User superuser status after de-assign", put_response.data['is_superuser'])
        assert not put_response.data['is_superuser']
