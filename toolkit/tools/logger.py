import logging
from toolkit.settings import INFO_LOGGER, ERROR_LOGGER

class Logger:

    def __init__(self):
        self.info_logger = logging.getLogger(INFO_LOGGER)
        self.error_logger = logging.getLogger(ERROR_LOGGER)
    
    def info(self, message):
        self.info_logger.info(message)
    
    def error(self, message, exec_info=None):
        if execution_info:
            self.error_logger.error(message, exc_info=exc)
        else:
            self.error_logger.error(message)
    