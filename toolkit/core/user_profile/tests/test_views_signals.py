from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.user_profile.models import UserProfile
from toolkit.utils.utils_for_tests import create_test_user

class UserProfileSignalsAndViewsTests(APITestCase):

    def setUp(self):
        # Create a new User
        self.user = create_test_user(name='user', password='pw')


    def test_profile_object(self):
        '''Test whether or not UserProfile object was created'''
        self.assertTrue(UserProfile.objects.filter(user=self.user.pk).exists())


    def test_profile_detail(self):
        '''Test if the UserProfile view is working'''
        # Project Owner should be able to activate
        url = f'/users/{self.user.profile.id}/'
        self.client.login(username='user', password='pw')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
