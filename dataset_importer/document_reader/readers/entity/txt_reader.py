from entity_reader import EntityReader

from dataset_importer.utils import HandleDatasetImportException


class TXTReader(EntityReader):

	@staticmethod
	def get_features(**kwargs):

		directory = kwargs['directory']

		for file_path in TXTReader.get_file_list(directory, 'txt'):
			try:
				features = TXTReader.get_meta_features(file_path=file_path)

				with open(file_path, 'r') as text_file:
					features['text'] = text_file.read()

				features['_texta_id'] = file_path
				yield features

			except Exception as e:
				HandleDatasetImportException(kwargs, e, file_path=file_path)

	@staticmethod
	def count_total_documents(**kwargs):
		directory = kwargs['directory']
		return TXTReader.count_documents(root_directory=directory, extension='txt')
