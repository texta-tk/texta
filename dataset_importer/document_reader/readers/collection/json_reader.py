from collection_reader import CollectionReader
import json

from dataset_importer.utils import HandleDatasetImportException


class JSONReader(CollectionReader):

	@staticmethod
	def get_features(**kwargs):

		directory = kwargs['directory']
		file_list = CollectionReader.get_file_list(directory, 'jsonl') + CollectionReader.get_file_list(directory, 'jl')
		for file_path in file_list:
			with open(file_path, 'r', encoding='utf8') as json_file:
				for line in json_file:
					try:
						features = json.loads(line.strip())
						yield features

					except Exception as e:
						HandleDatasetImportException(kwargs, e, file_path=file_path)

	@staticmethod
	def count_total_documents(**kwargs):
		directory = kwargs['directory']

		total_documents = 0

		for file_path in JSONReader.get_file_list(directory, 'json'):
			with open(file_path, encoding='utf8') as json_file:
				total_documents += sum(1 for row in json_file)

		return total_documents
