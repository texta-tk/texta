import logging
from django.conf import settings


class RequireLogstashInstance(logging.Filter):
	def filter(self, record):
		return bool(settings.USING_LOGSTASH)
