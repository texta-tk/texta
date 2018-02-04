import adapter


class DocumentReader(object):

    def __init__(self, available_formats=None, directory=None):
        self._available_formats = available_formats
        self._directory = directory

    def read_documents(self, **kwargs):
        reading_parameters = kwargs

        if self._available_formats:
            for format in reading_parameters['formats']:
                if format not in self._available_formats:
                    raise NotSupportedFormat(format)

        for format in reading_parameters['formats']:
            adapter = adapter_map[format]
            for features in adapter.get_features(**reading_parameters):
                yield features

    def count_total_documents(self, **kwargs):
        reading_parameters = kwargs

        if self._available_formats:
            for format in reading_parameters['formats']:
                if format not in self._available_formats:
                    raise NotSupportedFormat(format)

        total_docs = 0

        for format in reading_parameters['formats']:
            adapter = adapter_map[format]
            total_docs += adapter.count_total_documents(**kwargs)

        return total_docs




class NotSupportedFormat(Exception):
    pass


adapter_map = {}

try:
    adapter_map['csv'] = adapter.collection.csv.CSVAdapter
except:
    pass

try:
    adapter_map['xls'] = adapter.collection.excel.ExcelAdapter
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
    adapter_map['docx'] = adapter.entity.docx.DocXAdapter
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