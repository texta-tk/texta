import logging
from django.conf import settings


class RequireGraylogInstance(logging.Filter):
	def filter(self, record):
		return True if settings.USING_GRAYLOG == "True" else False
