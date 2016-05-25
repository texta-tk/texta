
import json
import logging

from settings import INFO_LOGGER, ERROR_LOGGER


class LogManager:

    def __init__(self, module_name, process):
        self.module_name = module_name
        self.process = process
        self.log_context = {}

    def info(self, event, msg=None):
        records_str = self._get_records_str(event, msg)
        logger = logging.getLogger(INFO_LOGGER)
        logger.info(records_str)

    def error(self, event, msg=None):
        records_str = self._get_records_str(event, msg)
        logger = logging.getLogger(ERROR_LOGGER)
        logger.error(records_str)

    def exception(self, event, msg=None):
        records_str = self._get_records_str(event, msg)
        logger = logging.getLogger(ERROR_LOGGER)
        logger.exception(records_str)

    def _build_header(self, event):
        msg = dict()
        msg['module'] = self.module_name
        msg['process'] = self.process
        msg['event'] = event
        return msg

    def _get_records_str(self, event, msg):
        records = self._build_header(event)
        records['context'] = self.log_context
        if msg:
            records['msg'] = msg
        records_str = json.dumps(records)
        return records_str

    def clean_context(self):
        self.log_context = {}

    def set_context(self, label, data):
        self.log_context[label] = data
