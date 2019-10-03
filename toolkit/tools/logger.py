import logging
from toolkit.settings import INFO_LOGGER, ERROR_LOGGER

class Logger:

    def __init__(self):
        self.info_logger = INFO_LOGGER
        self.error_logger = ERROR_LOGGER
    
    def info(self, message):
        logging.getLogger(self.info_logger).info(message)
    
    def error(self, message, execution_info=None):
        if execution_info:
            logging.getLogger(self.error_logger).error(message, exc_info=exc)
        else:
            logging.getLogger(self.error_logger).error(message)
    