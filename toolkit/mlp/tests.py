# Create your tests here.
import json

from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.test_settings import TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.tools.utils_for_tests import create_test_user, print_output

