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
        """Test whether UserProfile object was created"""
        user_profile = UserProfile.objects.filter(user=self.user.pk)
        self.assertTrue(user_profile.exists())
        user_profile = user_profile.last()
        self.assertTrue(getattr(user_profile, "uuid", False))  # Check that UUID is automatically filled in when user is created.


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


    def test_detail_view_contents(self):
        self.client.login(username="admin", password="1234")
        response = self.client.get(self.admin_url)
        data = response.data
        print_output("test_detail_view_contents:response.data", data)
        self.assertTrue(response.status_code, status.HTTP_200_OK)

        fields_to_check_in_user = ["profile", "display_name"]
        for field in fields_to_check_in_user:
            self.assertTrue(field in data)
            self.assertTrue(data[field])

        fields_to_check_in_user_profile = ["uuid"]
        user_profile = data["profile"]

        for field in fields_to_check_in_user_profile:
            self.assertTrue(field in user_profile)
            self.assertTrue(user_profile[field])


    def test_that_making_a_normal_user_a_superusers_adds_the_is_staff_flag(self):
        self.client.login(username="admin", password="1234")
        response = self.client.patch(self.user_url, data={"is_superuser": True}, format="json")
        print_output("test_that_making_a_normal_user_a_superusers_adds_the_is_staff_flag:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(username="user")
        self.assertEqual(user.is_staff, True)
