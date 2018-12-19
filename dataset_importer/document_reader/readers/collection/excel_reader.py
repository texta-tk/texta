import xlrd
from collection_reader import CollectionReader

from dataset_importer.utils import HandleDatasetImportException


class ExcelReader(CollectionReader):
	empty_and_blank_codes = {0}

	converters = {
		'text':    lambda string: string if string else '',
		'date':    lambda date: date if date else None,
		'bool':    lambda boolean_int: bool(boolean_int) if boolean_int in {0, 1} else None,
		'float':   lambda float_: float_,
		'int':     lambda float_: int(float_) if str(float_).isdigit() else None,
		'default': lambda val: str(val)
	}

	@staticmethod
	def get_features(**kwargs):
		directory = kwargs['directory']

		for file_extension in ['xls', 'xlsx']:
			for file_path in ExcelReader.get_file_list(directory, file_extension):

				try:
					book = xlrd.open_workbook(file_path)
					sheet = book.sheet_by_index(0)

					feature_labels = [cell.value if isinstance(cell.value, str) else str(cell.value) for cell in sheet.row(0)]
					feature_converters = []

					for column_idx in range(sheet.ncols):
						col_types = list(
							{col_type for col_type in sheet.col_types(column_idx)[1:]  # TODO [1:] will go out of range
							 if col_type not in ExcelReader.empty_and_blank_codes})
						col_values = sheet.col_values(column_idx)
						feature_converters.append(ExcelReader.get_column_converter(col_types, col_values))

					for row_idx, excel_row in ((row_idx, sheet.row(row_idx)) for row_idx in range(1, sheet.nrows)):
						document = {feature_labels[col_idx]: feature_converters[col_idx](cell.value) for col_idx, cell in enumerate(excel_row)}
						document['_texta_id'] = '{0}_{1}'.format(file_path, row_idx)
						yield document

				except Exception as e:
					HandleDatasetImportException(kwargs, e, file_path=file_path)

	@staticmethod
	def count_total_documents(**kwargs):
		directory = kwargs['directory']

		total_documents = 0

		for file_extension in ['xls', 'xlsx']:
			for file_path in ExcelReader.get_file_list(directory, file_extension):
				book = xlrd.open_workbook(file_path)
				sheet = book.sheet_by_index(0)
				total_documents += max(0, sheet.nrows - 1)

		return total_documents

	@staticmethod
	def get_column_converter(value_types, values):
		if len(value_types) == 1:
			code = value_types[0]
			if code == 1:
				return ExcelReader.converters['text']
			elif code == 2:
				if all(isinstance(value, int) for value in values):
					return ExcelReader.converters['int']
				else:
					return ExcelReader.converters['float']
			elif code == 3:
				return ExcelReader.converters['date']
			elif code == 4:
				return ExcelReader.converters['bool']
			else:
				return ExcelReader.converters['default']
		elif len(value_types) == 2:
			if 2 in value_types and 4 in value_types:
				if all(isinstance(value, int) for value in values):
					return ExcelReader.converters['int']
				else:
					return ExcelReader.converters['float']
			else:
				return ExcelReader.converters['default']
		else:
			return ExcelReader.converters['default']
