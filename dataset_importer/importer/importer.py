"""This module contains most of the logic and workflow behind importing datasets.
"""

import time
import os
import platform
from datetime import datetime
import re
import shutil
import requests
import pathlib
import json
import logging
from django.conf import settings
from dataset_importer.document_storer.storer import DocumentStorer
from dataset_importer.document_reader.reader import DocumentReader, entity_reader_map, collection_reader_map, database_reader_map
from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map
from dataset_importer.archive_extractor.extractor import ArchiveExtractor, extractor_map
from threading import Lock
from multiprocessing.pool import ThreadPool as Pool
from dataset_importer.models import DatasetImport
from dataset_importer.syncer.SQLiteIndex import SQLiteIndex

if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

DAEMON_BASED_DATABASE_FORMATS = set(database_reader_map) - {'sqlite'}
ARCHIVE_FORMATS = set(extractor_map)


class DatasetImporter(object):
    """The class behind importing. The functions in this module that are not methods in this class is due to the Python 2.7's
    limited capability of serializing class methods. In Python 3.x, they should end up in this class.
    """

    def __init__(self, es_url, configuration, data_access_object, file_system_storer):
        """
        :param es_url: Elasticsearch instance's URL.
        :param configuration: DATASET_IMPORTER dict from texta/settings.py, which includes necessary parameters for importer.
        :param data_access_object: An attempt to separate Django's DatasetImport model object from import to reduce coupling and enhance testing.
        :param file_system_storer: Same as above. Django's built-in FileSystemStorage for storing data from requests to disk.
        :type es_url: string
        :type configuration: dict
        """
        self._es_url = es_url

        self._root_directory = configuration['directory']
        self._n_processes = configuration['import_processes']
        self._process_batch_size = configuration['process_batch_size']
        self._index_sqlite_path = configuration['sync']['index_sqlite_path']

        self._dao = data_access_object
        self._file_system_storer = file_system_storer

        self._active_import_jobs = {}

    def import_dataset(self, request):
        """Performs a dataset import session with all of the workflow - data acquisition, extraction, reading,
        preprocessing, and storing.

        :param request: Django request
        """
        self._validate_request(request)

        parameters = self.django_request_to_import_parameters(request.POST)
        parameters = self._preprocess_import(parameters, request.user, request.FILES)

        process = Process(target=_import_dataset, args=(parameters, self._n_processes, self._process_batch_size)).start()

        self._active_import_jobs[parameters['import_id']] = {
            'process': process,
            'parameters': parameters
        }

    def reimport(self, parameters):
        """import_dataset's equivalent without the Django request validation and transformation to Importer's parameter dict.
        Used mostly by Syncer or if reimport is added to GUI.

        :param parameters: Dataset Importer parameters which have been validated during a previous run.
        :type parameters: dict
        """
        parameters = self._preprocess_reimport(parameters=parameters)
        Process(target=_import_dataset, args=(parameters, self._n_processes, self._process_batch_size)).start()
        # _import_dataset(parameters, n_processes=self._n_processes, process_batch_size=self._process_batch_size)

    def cancel_import_job(self, import_id):
        """Cancels an active import job.

        :param import_id: ID of the cancelled job.
        :type import_id: int or string holding an int
        """
        import_dict = self._active_import_jobs.get(int(import_id), None)

        if import_dict:
            import_process = import_dict.get('process', None)
            if import_process:
                import_process.terminate()

            if import_dict['is_local'] is False:
                shutil.rmtree(import_dict['directory'])

        try:
            dataset_import = self._dao.objects.get(pk=import_id)
            dataset_import.finished = True
            dataset_import.status = 'Cancelled'
            dataset_import.save()
        except Exception:
            logging.getLogger(settings.ERROR_LOGGER).exception("Could not save to Django DB.")
            pass

    def _preprocess_import(self, parameters, request_user, files_dict):
        """Alters parameters to meet importer's needs.

        :param parameters: initial request parameters.
        :param request_user: Django user, who initiated the request.
        :param files_dict: request files.
        :type parameters: dict
        :return: aletered parameters
        :rtype: dict
        """
        parameters['formats'] = json.loads(parameters.get('formats', '[]'))
        parameters['preprocessors'] = json.loads(parameters.get('preprocessors', '[]'))
        parameters['is_local'] = True if parameters.get('host_directory', None) else False
        parameters['keep_synchronized'] = self._determine_if_should_synchronize(parameters=parameters)
        parameters['remove_existing_dataset'] = True if parameters.get('remove_existing_dataset', 'false') == 'true' else False
        parameters['storer'] = 'elastic'

        parameters['archives'], parameters['formats'] = self._separate_archive_and_reader_formats(parameters)

        parameters['directory'] = self._prepare_import_directory(
            root_directory=self._root_directory,
            source_directory=parameters.get('host_directory', None)
        )

        if any(format not in DAEMON_BASED_DATABASE_FORMATS for format in parameters['formats']):
            if 'file' in files_dict and parameters.get('is_local', False) is False:
                parameters['file_path'] = self._store_file(os.path.join(parameters['directory'], files_dict['file'].name),
                                                           files_dict['file'])

        parameters['import_id'] = self._create_dataset_import(parameters, request_user)

        parameters['texta_elastic_url'] = self._es_url
        parameters['index_sqlite_path'] = self._index_sqlite_path

        return parameters

    def _separate_archive_and_reader_formats(self, parameters):
        """Splits initial formats to archives and formats to reduce the complexity for later processes.

        :param parameters: dataset import's parameters.
        :type parameters: dict
        """
        archives = []
        reader_formats = []

        for file_type in parameters['formats']:
            if file_type in ARCHIVE_FORMATS:
                archives.append(file_type)
            else:
                reader_formats.append(file_type)

        return archives, reader_formats

    def _preprocess_reimport(self, parameters):
        """Reimport's alternative to _preprocess_import. Most of the necessary alterations have been done by _preprocess_import
        during some previous import session.

        :param parameters: previously altered parameters.
        :return: altered parameters for current session.
        """
        parameters['directory'] = self._prepare_import_directory(self._root_directory)

        return parameters

    def django_request_to_import_parameters(self, post_request_dict):
        """Convert Django's Request to dict suitable for Dataset Importer.

        :param post_request_dict: Django's request.POST
        :return: dict corresponding to post_request_dict
        :rtype: dict
        """
        return {key: (value if not isinstance(value, list) else value[0]) for key, value in post_request_dict.items()}

    def _validate_request(self, request):
        """Request validation procedure.

        :param request: Django's Request.
        :raises: Exception, if parameters are invalid.
        """
        if 'file' not in request.FILES and 'url' not in request.POST or request.POST.get('is_local', False) is False:
            # raise Exception('Import failed.')
            pass

    def _determine_if_should_synchronize(self, parameters):
        """Secondary synchronization validation in case some parameters are in conflict with synchronization.

        :param parameters: preprocessed paramters.
        :return: True, if synchronization is viable based on the parameters, False otherwise.
        """
        if parameters.get('keep_synchronized', 'false') == 'true':
            if parameters.get('is_local', False) is True:
                return True
            elif parameters.get('url', None):
                return True
            elif all(format in DAEMON_BASED_DATABASE_FORMATS for format in parameters.get('format', [])): # OR should sync syncables?
                return True
            else:
                return False
        else:
            return False

    def _create_dataset_import(self, parameters, request_user):
        """Adds a new dataset import entry to database using data access object.

        :param parameters: dataset import parameters.
        :param request_user: Django user who initiated the request.
        :type parameters: dict
        :return: dataset ID of the added dataset import entry
        :rtype: int
        """
        dataset_import = self._dao.objects.create(
            source_type=self._get_source_type(parameters.get('format', ''), parameters.get('archive', '')),
            source_name=self._get_source_name(parameters),
            elastic_index=parameters.get('texta_elastic_index', ''), elastic_mapping=parameters.get('texta_elastic_mapping', ''),
            start_time=datetime.now(), end_time=None, user=request_user, status='Processing', finished=False,
            must_sync=parameters.get('keep_synchronized', False)
        )
        dataset_import.save()

        return dataset_import.pk

    def _prepare_import_directory(self, root_directory, source_directory=None):
        """Creates a 'temporary' directory for storing import data. Doesn't use native temporary solution due to
        permission issues. If files are imported from a local directory, they are first copied the temporary directory.

        :param root_directory: directory where to store subdirectories with dataset import data.
        :param source_directory: local directory from where to copy the files. Optional.
        :type root_directory: string
        :type source_directory: string
        :return: path to the import session's directory.
        :rtype: string
        """
        temp_folder_name = str(int(time.time() * 1000000))
        temp_folder_path = os.path.join(root_directory, temp_folder_name)

        if source_directory:
            shutil.copytree(src=source_directory, dst=temp_folder_path)
        else:
            os.makedirs(temp_folder_path)

        return temp_folder_path

    def _store_file(self, file_name, file_content):
        """Stores file to disk.

        :param file_name: name of the file
        :param file_content: binary content of the file
        :type file_name: string
        :type file_content: binary string
        :return: path to the stored file
        """
        fs = self._file_system_storer(location=self._root_directory)
        file_name = fs.save(file_name, file_content)
        return fs.path(file_name)

    def _get_source_type(self, format, archive):
        source_type_parts = [format]
        if archive:
            source_type_parts.append('|')
            source_type_parts.append(archive)

        return ''.join(source_type_parts)

    def _get_source_name(self, parameters):
        if 'file_path' in parameters:
            return os.path.basename(parameters['file_path'])
        elif 'url' in parameters:
            return parameters['url']
        else:
            return ''


def _import_dataset(parameter_dict, n_processes, process_batch_size):
    """Starts the import process from a parallel process.

    :param parameter_dict: dataset importer's parameters.
    :param n_processes: size of the multiprocessing pool.
    :param process_batch_size: the number of documents to process at any given time by a process.
    :type parameter_dict: dict
    :type n_processes: int
    :type process_batch_size: int
    """
    # Local files are not extracted from archives due to directory permissions
    # If importing from local hard drive, extract first.
    if parameter_dict['is_local'] is False:
        if 'file_path' not in parameter_dict:
            parameter_dict['file_path'] = download(parameter_dict['url'], parameter_dict['directory'])

        _extract_archives(parameter_dict)

    reader = DocumentReader()
    _set_total_documents(parameter_dict=parameter_dict, reader=reader)
    _run_processing_jobs(parameter_dict=parameter_dict, reader=reader, n_processes=n_processes, process_batch_size=process_batch_size)


def _extract_archives(parameter_dict):
    """Extracts archives based on the information from the parameters.

    :param parameter_dict: dataset importer parameters.
    :type parameter_dict: dict
    """
    archive_formats = parameter_dict.get('archives', [])

    if not archive_formats:
        return

    unprocessed_archives = ArchiveExtractor.detect_archives(
        root_directory=parameter_dict['directory'],
        archive_formats=archive_formats
    )

    while unprocessed_archives:
        for unprocessed_archive in unprocessed_archives:
            ArchiveExtractor.extract_archive(
                file_path=unprocessed_archive['path'],
                archive_format=unprocessed_archive['format']
            )

        unprocessed_archives = ArchiveExtractor.detect_archives(
            root_directory=parameter_dict['directory'],
            archive_formats=archive_formats
        )


def _init_pool(lock_):
    """Hack to allow locks in a multiprocessing pool.
    """
    global lock
    lock = lock_


def _set_total_documents(parameter_dict, reader):
    """Updates total documents count in the database entry.

    :param parameter_dict: dataset import's parameters.
    :param reader: dataset importer's document reader.
    """
    dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
    dataset_import.total_documents = reader.count_total_documents(**parameter_dict)
    dataset_import.save()


def _complete_import_job(parameter_dict):
    """Updates database entry to completed status.

    :param parameter_dict: dataset import's parameters.
    """
    import_id = parameter_dict['import_id']
    dataset_import = DatasetImport.objects.get(pk=import_id)
    dataset_import.end_time = datetime.now()
    dataset_import.status = 'Completed'
    dataset_import.json_parameters = json.dumps(parameter_dict)
    dataset_import.save()


def _processing_job(documents, parameter_dict):
    """A single processing job on a parallel node, which processes a batch of documents.

    :param documents: batch of documents to process.
    :param parameter_dict: dataset import's parameters.
    :type documents: list of dicts
    :type parameter_dict: dict
    """
    dataset_name = '{0}_{1}'.format(parameter_dict['texta_elastic_index'], parameter_dict['texta_elastic_mapping'])

    # Find unprocessed documents
    original_ids = [document['_texta_id'] for document in documents]
    index = SQLiteIndex(sqlite_file_path=parameter_dict['index_sqlite_path'])
    new_ids = set(index.get_new_entries(dataset=dataset_name, candidate_values=original_ids))
    documents = [document for document in documents if document['_texta_id'] in new_ids]

    for document in documents:
        del document['_texta_id']

        try:
            processed_documents = list(DocumentPreprocessor.process(documents=documents, **parameter_dict))

            storer = DocumentStorer.get_storer(**parameter_dict)
            stored_documents_count = storer.store(processed_documents)
            if processed_documents:
                with lock:
                    dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
                    dataset_import.processed_documents += stored_documents_count
                    dataset_import.save()

                    index.add(dataset=dataset_name, values=new_ids)

        except Exception as e:
            file_path = pathlib.Path(parameter_dict.get('file_path', ''))
            error_message = "{0} Error:\n{1}".format(file_path.name, str(repr(e)))
            current_import = DatasetImport.objects.get(id=parameter_dict.get('import_id'))

            # Save the string when it's empty, append to the previous when it has something.
            current_import.error += error_message
            current_import.save()
            pass


def _remove_existing_dataset(parameter_dict):
    """Removes imported dataset from stored location and from Synchronizer's index.

    :param parameter_dict: dataset import's parameters
    :type parameter_dict: dict
    """
    storer = DocumentStorer.get_storer(**parameter_dict)
    storer.remove()
    dataset_name = '{0}_{1}'.format(parameter_dict['texta_elastic_index'], parameter_dict['texta_elastic_mapping'])
    SQLiteIndex(sqlite_file_path=parameter_dict['index_sqlite_path']).remove(dataset_name)


def _run_processing_jobs(parameter_dict, reader, n_processes, process_batch_size):
    """Creates document batches and dispatches them to processing nodes.

    :param parameter_dict: dataset import's parameters.
    :param reader: dataset importer's document reader.
    :param n_processes: size of the multiprocessing pool.
    :param process_batch_size: the number of documents to process at any given time by a node.
    :type parameter_dict: dict
    :type n_processes: int
    :type process_batch_size: int
    """
    if parameter_dict.get('remove_existing_dataset', False):
        _remove_existing_dataset(parameter_dict)

    import_job_lock = Lock()

    process_pool = Pool(processes=n_processes, initializer=_init_pool, initargs=(import_job_lock,))
    batch = []

    for document in reader.read_documents(**parameter_dict):
        batch.append(document)

        # Send documents when they reach their batch size and empty it.
        if len(batch) == process_batch_size:
            process_pool.apply(_processing_job, args=(batch, parameter_dict))
            batch = []

    # Send the final documents that did not reach the batch size.
    if batch:
        process_pool.apply(_processing_job, args=(batch, parameter_dict))

    process_pool.close()
    process_pool.join()

    _complete_import_job(parameter_dict)


def download(url, target_directory, chunk_size=1024):
    """Download data source from a remote host.

    :param url: URL to the data source.
    :param target_directory: import session's directory path to download the data source.
    :param chunk_size: data stream's chunk size
    :type url: string
    :type target_directory: string
    :type chunk_size: int
    :return: path to the downloaded file
    :rtype: string
    """
    head_response = requests.head(url)

    file_name = _derive_file_name(head_response, url)
    file_path = os.path.join(target_directory, file_name)

    response = requests.get(url, stream=True)
    with open(file_path, 'wb') as downloaded_file:
        for chunk in response.iter_content(chunk_size):
            if chunk:
                downloaded_file.write(chunk)

    return file_path

def tear_down_import_directory(import_directory_path):
    shutil.rmtree(import_directory_path)


def _derive_file_name(response, url):
    """Tries to derive file name from either response header or URL string.

    :param response: requests Response
    :param url: URL of the downloaded file
    :type url: string
    :return: name of the new file
    :rtype: string
    """
    file_name = ''

    if 'content-disposition' in response.headers:
        file_names = re.findall('filename=(.*)', response['content-disposition'])

        if file_names:
            file_name = file_names[0].strip('\'" ')
    elif 'location' in response.headers:
        file_name = os.path.basename(response.headers['location'])

    if not file_name:
        file_name = os.path.basename(url)

    return file_name

