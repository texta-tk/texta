from django.contrib.auth.models import User
from django.test import TestCase, Client


# Create your tests here.
class ImporterAPITestCase(TestCase):

	def setUp(self):
		c = Client()
		User.profile.create_superuser(username="admin", password="K!ll!987654321")

	def test_auth_token_validation(self):
		pass

	def test_missing_field_validation(self):
		pass

	def test_missing_value_validation(self):
		pass
