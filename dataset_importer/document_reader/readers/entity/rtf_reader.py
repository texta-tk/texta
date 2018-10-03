from entity_reader import EntityReader
import textract

from dataset_importer.utils import HandleDatasetImportException


class RTFReader(EntityReader):

	@staticmethod
	def get_features(**kwargs):

		directory = kwargs['directory']

		for file_path in RTFReader.get_file_list(directory, 'rtf'):
			try:
				features = RTFReader.get_meta_features(file_path=file_path)
				features['text'] = textract.process(file_path).decode('utf8')
				features['_texta_id'] = file_path

				yield features

			except Exception as e:
				HandleDatasetImportException(kwargs, e, file_path=file_path)

	@staticmethod
	def count_total_documents(**kwargs):
		directory = kwargs['directory']
		return RTFReader.count_documents(root_directory=directory, extension='rtf')
