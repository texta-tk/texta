import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

try:
    import csv_reader as csv
except:
    print('failed to import csv_reader as csv')

try:
    import excel_reader as excel
except:
    print('failed to import excel_reader as excel')

try:
    import json_reader as json
except:
    print('failed to import json_reader as json')

try:
    import xml_reader as xml
except:
    print('failed to import xml_reader as xml')