import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import readers


def log_reader_status(code, status):
    print('[Dataset Importer] {code} reader {status}.'.format(**{'code': code, 'status': status}))


entity_reader_map = {}

try:
    entity_reader_map['doc'] = {
        'name': 'DOC',
        'parameter_tags': 'file',
        'class': readers.entity.doc.DocReader
    }
    log_reader_status(code='.doc', status='enabled')
except:
    log_reader_status(code='.doc', status='disabled')

try:
    entity_reader_map['docx'] = {
        'name': 'DOCX',
        'parameter_tags': 'file',
        'class': readers.entity.docx.DocXReader
    }
    log_reader_status(code='.docx', status='enabled')
except:
    log_reader_status(code='.docx', status='disabled')

try:
    entity_reader_map['html'] = {
        'name': 'HTML',
        'parameter_tags': 'file',
        'class': readers.entity.html.HTMLAdapter
    }
    log_reader_status(code='.html', status='enabled')
except:
    log_reader_status(code='.html', status='disabled')

try:
    entity_reader_map['pdf'] = {
        'name': 'PDF',
        'parameter_tags': 'file',
        'class': readers.entity.pdf.PDFReader
    }
    log_reader_status(code='.pdf', status='enabled')
except:
    log_reader_status(code='.pdf', status='disabled')

try:
    entity_reader_map['rtf'] = {
        'name': 'RTF',
        'parameter_tags': 'file',
        'class': readers.entity.rtf.RTFReader
    }
    log_reader_status(code='.rtf', status='enabled')
except:
    log_reader_status(code='.rtf', status='disabled')

try:
    entity_reader_map['txt'] = {
        'name': 'TXT',
        'parameter_tags': 'file',
        'class': readers.entity.txt.TXTReader
    }
    log_reader_status(code='.txt', status='enabled')
except:
    log_reader_status(code='.txt', status='disabled')


collection_reader_map = {}


try:
    collection_reader_map['csv'] = {
        'name': 'CSV',
        'parameter_tags': 'file',
        'class': readers.collection.csv.CSVReader
    }
    log_reader_status(code='.csv', status='enabled')
except:
    log_reader_status(code='.csv', status='disabled')

try:
    collection_reader_map['xls'] = {
        'name': 'XLS/XLSX',
        'parameter_tags': 'file',
        'class': readers.collection.excel.ExcelReader
    }
    log_reader_status(code='.xls', status='enabled')
except:
    log_reader_status(code='.xls', status='disabled')

try:
    collection_reader_map['json'] = {
        'name': 'JSON',
        'parameter_tags': 'file',
        'class': readers.collection.json.JSONReader
    }
    log_reader_status(code='.json', status='enabled')
except:
    log_reader_status(code='.json', status='disabled')

try:
    collection_reader_map['xml'] = {
        'name': 'XML',
        'parameter_tags': 'file,xml',
        'class': readers.collection.xml.XMLReader
    }
    log_reader_status(code='.xml', status='enabled')
except:
    log_reader_status(code='.xml', status='disabled')


database_reader_map = {}


try:
    database_reader_map['elastic'] = {
        'name': 'Elasticsearch',
        'parameter_tags': 'elastic',
        'class': readers.database.elastic.ElasticReader
    }
    log_reader_status(code='elastic', status='enabled')
except:
    log_reader_status(code='elastic', status='disabled')

try:
    database_reader_map['mongodb'] = {
        'name': 'MongoDB',
        'parameter_tags': 'mongodb',
        'class': readers.database.mongodb.MongoDBReader
    }
    log_reader_status(code='mongodb', status='enabled')
except:
    log_reader_status(code='mongodb', status='disabled')

try:
    database_reader_map['postgres'] = {
        'name': 'PostgreSQL',
        'parameter_tags': 'postgres',
        'class': readers.database.postgres.PostgreSQLReader
    }
    log_reader_status(code='postgres', status='enabled')
except:
    log_reader_status(code='postgres', status='disabled')

try:
    database_reader_map['sqlite'] = {
        'name': 'SQLite',
        'parameter_tags': 'sqlite,file',
        'class': readers.database.sqlite.SQLiteReader
    }
    log_reader_status(code='.sqlite', status='enabled')
except:
    log_reader_status(code='.sqlite', status='disabled')

print('')
