import json
import pathlib
import logging
import multiprocessing

from dataset_importer.models import DatasetImport
from django.conf import settings


def HandleDatasetImportException(parameter_dict: dict, exception: Exception, file_path=''):
	"""
	Sets the logic on how to handle Exceptions that rise during the reading
	phase of documents or preprocessing of features.

	Filepath and error message will be saved to the relevant instance of the
	DatasetImporter model.

	:param parameter_dict: Data from the dataset import like filepath, import_id, form parameters etc.
	:param file_path: Name of the file which failed to be read/processed.
	:param exception: Exception object caught during an... exception.
	:return: null
	"""
	current_import = DatasetImport.objects.get(id=parameter_dict.get('import_id'))

	# Not all cases send a file_path, like database connections etc.
	if file_path:
		file_path = pathlib.Path(file_path)
		error_message = {'file': str(file_path.name), 'error': str(repr(exception))}
	else:
		error_message = {'error': str(repr(exception))}

	# Get and parse the error json, if it's an empty string (as in first error), return a list.
	# All errors will be saved as a list.
	error_field = json.loads(current_import.errors) if current_import.errors else []
	error_field.append(error_message)
	current_import.errors = json.dumps(error_field)
	current_import.save()

	logging.getLogger(settings.ERROR_LOGGER).exception("Failed to import.", extra={'file': file_path})

