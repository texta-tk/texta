import adapter


class DocumentReader(object):

    def __init__(self, available_formats=None, directory=None):
        self._available_formats = available_formats
        self._directory = directory

    def read_documents(self, **kwargs):
        if self._available_formats and format not in self._available_formats:
            raise NotSupportedFormat()

        reading_parameters = kwargs

        adapter = adapter_map[reading_parameters['format']]

        return adapter.get_features(**reading_parameters)


class NotSupportedFormat(Exception):
    pass


adapter_map = {}

try:
    adapter_map['csv'] = adapter.collection.csv.CSVAdapter
except:
    pass

try:
    adapter_map['excel'] = adapter.collection.excel.ExcelAdapter
except:
    pass

try:
    adapter_map['json'] = adapter.collection.json.JSONAdapter
except:
    pass

try:
    adapter_map['xml'] = adapter.collection.xml.XMLAdapter
except:
    pass

try:
    adapter_map['elastic'] = adapter.database.elastic.ElasticAdapter
except:
    pass

try:
    adapter_map['mongodb'] = adapter.database.mongodb.MongoDBAdapter
except:
    pass

try:
    adapter_map['postgres'] = adapter.database.postgres.PostgreSQLAdapter
except:
    pass

try:
    adapter_map['sqlite'] = adapter.database.sqlite.SQLiteAdapter
except:
    pass

try:
    adapter_map['doc'] = adapter.entity.doc.DocAdapter
except:
    pass

try:
    adapter_map['html'] = adapter.entity.html.HTMLAdapter
except:
    pass

try:
    adapter_map['pdf'] = adapter.entity.pdf.PDFAdapter
except:
    pass

try:
    adapter_map['rtf'] = adapter.entity.rtf.RTFAdapter
except:
    pass

try:
    adapter_map['txt'] = adapter.entity.txt.TXTAdapter
except:
    pass