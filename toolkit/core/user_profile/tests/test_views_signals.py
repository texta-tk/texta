from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from toolkit.core.user_profile.models import UserProfile
from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


class UserProfileSignalsAndViewsTests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        # Create admin user with pk 1
        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        self.admin.save()
        # Create a new User
        self.user = create_test_user(name='user', password='pw')
        self.user_url = f'{TEST_VERSION_PREFIX}/users/{self.user.profile.id}/'
        self.admin_url = f'{TEST_VERSION_PREFIX}/users/{self.admin.profile.id}/'


    def test_run(self):
        self.run_profile_object()
        self.run_profile_login()
        self.assign_superuser()


    def run_profile_object(self):
        """Test whether or not UserProfile object was created"""
        self.assertTrue(UserProfile.objects.filter(user=self.user.pk).exists())


    def run_profile_login(self):
        """Test if the UserProfile view is working"""
        self.client.login(username='user', password='pw')
        response = self.client.get(self.user_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def assign_superuser(self):
        assign_payload = {
            "is_superuser": True
        }

        deassign_payload = {
            "is_superuser": False
        }

        self.client.login(username='admin', password='1234')
        # check that user is not superuser
        print_output("User superuser status before assign", self.user.is_superuser)
        assert not self.user.is_superuser

        # can't assign original admin
        put_response = self.client.put(self.admin_url, assign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_403_FORBIDDEN)
        print_output("assign superuser response data", put_response.data)

        # assign superuser status to user
        put_response = self.client.put(self.user_url, assign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        print_output("assign superuser response data", put_response.data)

        # check that user is superuser
        print_output("User superuser status after assign", put_response.data['is_superuser'])
        assert put_response.data['is_superuser']

        # de-assign superuser
        put_response = self.client.put(self.user_url, deassign_payload)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        print_output("de-assign superuser response data", put_response.data)

        # check that superuser status was removed
        print_output("User superuser status after de-assign", put_response.data['is_superuser'])
        assert not put_response.data['is_superuser']


    def test_admin_account_deletion(self):
        self.client.login(username="admin", password="1234")
        self.client.delete(self.user_url)

        deleted_user = User.objects.filter(username="user").count()
        self.assertTrue(deleted_user == 0)


    def test_normal_user_account_deletion(self):
        self.client.login(username="user", password="pw")
        response = self.client.delete(self.admin_url)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
