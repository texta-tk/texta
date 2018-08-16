from .settings import entity_reader_map, collection_reader_map, database_reader_map
from dataset_importer.models import DatasetImport
import pathlib
import json


class DocumentReader(object):
	"""A static document reader adapter that dispatches the document reading request to appropriate reader implementations.
	"""

	@staticmethod
	def read_documents(**kwargs):
		"""Applies document reader of appropriate type to each of the provided file_type. Document readers read files of
		their respective file_type and extract a features dictionary from the read document.

		:param kwargs: must contain a list of formats and parameters necessary for independent reader implementations.
		:return: dicts
		:rtype: dict generator
		"""

		reading_parameters = kwargs

		for file_type in reading_parameters['formats']:
			reader = reader_map[file_type]['class']

			for features in reader.get_features(**reading_parameters):
				yield features



	@staticmethod
	def count_total_documents(**kwargs):
		"""Delegates each appropriate reader implementation to count the number of documents of the respective format.
		Retrieves the total number of documents of which format is in formats list.

		:param kwargs: must contain a list of formats.
		:return: total number of documents within the dataset according to the appropriate format readers.
		"""
		reading_parameters = kwargs

		total_docs = 0

		for file_type in reading_parameters['formats']:
			reader = reader_map[file_type]['class']
			total_docs += reader.count_total_documents(**kwargs)

		return total_docs


def merge_dictionaries(*args):
	"""Takes an arbitrary number of dictionaries and returns a union of them.

	Does not handle key conflicts.

	:param args: arbitrary number of dictionaries
	:return: union of the provided dictionaries
	:rtype: dict
	"""
	final_dictionary = {}
	for current_dictionary in args:
		for key, value in current_dictionary.items():
			final_dictionary[key] = value

	return final_dictionary


reader_map = merge_dictionaries(entity_reader_map, collection_reader_map, database_reader_map)
