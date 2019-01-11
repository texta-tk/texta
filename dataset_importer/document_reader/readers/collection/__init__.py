import os, sys
from texta.settings import ERROR_LOGGER
import logging

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

try:
    import csv_reader as csv
except Exception as e:
    print('failed to import csv_reader as csv')
    logging.getLogger(ERROR_LOGGER).exception(e)

try:
    import excel_reader as excel
except Exception as e:
    print('failed to import excel_reader as excel')
    logging.getLogger(ERROR_LOGGER).exception(e)

try:
    import json_reader as json
except Exception as e:
    print('failed to import json_reader as json')
    logging.getLogger(ERROR_LOGGER).exception(e)

try:
    import xml_reader as xml
except Exception as e:
    print('failed to import xml_reader as xml')
    logging.getLogger(ERROR_LOGGER).exception(e)
