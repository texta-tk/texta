import time
import os
from datetime import datetime
import re
import shutil
import requests
import json
from dataset_importer.document_storer.storer import DocumentStorer
from dataset_importer.document_reader.reader import DocumentReader
from dataset_importer.document_processor.processor import DocumentProcessor
from dataset_importer.archive_extractor.extractor import ArchiveExtractor
from multiprocessing import Pool, Lock
from dataset_importer.models import DatasetImport
from dataset_importer.syncer.SQLiteIndex import SQLiteIndex

DAEMON_BASED_DATABASE_FORMATS = {'postgres', 'mongodb', 'elastic'}


class DatasetImporter(object):

    def __init__(self, es_url, configuration, data_access_object, file_system_storer):
        self._es_url = es_url

        self._root_directory = configuration['directory']
        self._n_processes = configuration['import_processes']
        self._process_batch_size = configuration['process_batch_size']
        self._enabled_input_types = self._get_verified_input_types(configuration['enabled_input_types'])
        self._index_sqlite_path = configuration['sync']['index_sqlite_path']

        self._dao = data_access_object
        self._file_system_storer = file_system_storer

        self._active_import_jobs = {}

    def import_dataset(self, request):
        self._validate_request(request)

        parameters = self.django_request_to_import_parameters(request.POST)
        parameters = self._preprocess_import(parameters, request.user, request.FILES)

        # process = Process(target=_import_dataset, args=(parameters, self._n_processes, self._process_batch_size)).start()
        process = None
        _import_dataset(parameters, n_processes=self._n_processes, process_batch_size=self._process_batch_size)

        self._active_import_jobs[parameters['import_id']] = {
            'process': process,
            'parameters': parameters
        }

    def reimport(self, parameters):
        parameters = self._preprocess_reimport(parameters=parameters)
        # Process(target=_import_dataset, args=(parameters, self._n_processes, self._process_batch_size)).start()
        _import_dataset(parameters, n_processes=self._n_processes, process_batch_size=self._process_batch_size)

    def cancel_import_job(self, import_id):
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
        except:
            pass

    def _preprocess_import(self, parameters, request_user, files_dict):
        parameters['is_local'] = True if parameters.get('directory', None) else False
        parameters['keep_synchronized'] = self._determine_if_should_synchronize(parameters=parameters)

        if parameters['is_local'] is False:
            parameters['directory'] = self._prepare_import_directory(self._root_directory)

        if parameters['format'] not in DAEMON_BASED_DATABASE_FORMATS:
            if 'file' in files_dict and parameters.get('is_local', False) is False:
                parameters['file_path'] = self._store_file(os.path.join(parameters['directory'], files_dict['file'].name),
                                                           files_dict['file'])

        parameters['import_id'] = self._create_dataset_import(parameters, request_user)

        parameters['elastic_url'] = self._es_url
        parameters['index_sqlite_path'] = self._index_sqlite_path

        return parameters

    def _preprocess_reimport(self, parameters):
        if parameters['is_local'] is False:
            parameters['directory'] = self._prepare_import_directory(self._root_directory)

        return parameters

    def django_request_to_import_parameters(self, post_request_dict):
        return {key: (value if not isinstance(value, list) else value[0]) for key, value in post_request_dict.items()}

    def _validate_request(self, request):
        if 'file' not in request.FILES and 'url' not in request.POST or request.POST.get('is_local', False) is False:
            # raise Exception('Import failed.')
            pass

    def _determine_if_should_synchronize(self, parameters):
        if parameters.get('keep_synchronized', 'false') == 'true':
            if parameters.get('is_local', False) is True:
                return True
            elif parameters.get('url', None):
                return True
            elif parameters.get('format', None) in DAEMON_BASED_DATABASE_FORMATS:
                return True
            else:
                return False
        else:
            return False

    def _create_dataset_import(self, parameters, request_user):
        dataset_import = self._dao.objects.create(
            source_type=self._get_source_type(parameters.get('format', ''), parameters.get('archive', '')),
            source_name=self._get_source_name(parameters),
            elastic_index=parameters.get('elastic_index', ''), elastic_mapping=parameters.get('elastic_mapping', ''),
            start_time=datetime.now(), end_time=None, user=request_user, status='Processing', finished=False,
            must_sync=parameters.get('keep_synchronized', False)
        )
        dataset_import.save()

        return dataset_import.pk

    def _prepare_import_directory(self, directory_path):
        temp_folder_name = str(int(time.time() * 1000000))
        temp_folder_path = os.path.join(directory_path, temp_folder_name)
        os.makedirs(temp_folder_path)

        return temp_folder_path

    def _get_verified_input_types(self, input_types):
        # TODO verify that input type processor is working/installed
        for type_category in input_types:
            for input_type in type_category:
                pass

        return input_types

    def _store_file(self, file_name, file_content):
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
    # Local files are not extracted from archives due to directory permissions
    # If importing from local hard drive, extract first.
    print(parameter_dict)
    if parameter_dict['is_local'] is False:
        if 'file_path' not in parameter_dict:
            parameter_dict['file_path'] = download(parameter_dict['url'], parameter_dict['directory'])

        if 'archive' in parameter_dict:
            ArchiveExtractor.extract_archive(
                file_path=parameter_dict['file_path'],
                archive_format=parameter_dict['archive']
            )

    reader = DocumentReader(directory=parameter_dict['directory'])
    _set_total_documents(parameter_dict=parameter_dict, reader=reader)
    _run_processing_jobs(parameter_dict=parameter_dict, reader=reader, n_processes=n_processes,
                         process_batch_size=process_batch_size)

    # if parameter_dict['is_local'] is False:
    #     shutil.rmtree(parameter_dict['directory'])


def _init_pool(lock_):
    global lock
    lock = lock_


def _set_total_documents(parameter_dict, reader):
    dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
    dataset_import.total_documents = reader.count_total_documents(**parameter_dict)
    dataset_import.save()


def _complete_import_job(parameter_dict):
    import_id = parameter_dict['import_id']
    dataset_import = DatasetImport.objects.get(pk=import_id)
    dataset_import.end_time = datetime.now()
    dataset_import.status = 'Completed'
    dataset_import.json_parameters = json.dumps(parameter_dict)
    dataset_import.save()


def _processing_job(documents, parameter_dict):
    dataset_name = '{0}_{1}'.format(parameter_dict['elastic_index'], parameter_dict['elastic_mapping'])
    original_ids = [document['_texta_id'] for document in documents]
    index = SQLiteIndex(sqlite_file_path=parameter_dict['index_sqlite_path'])
    new_ids = set(index.get_new_entries(dataset=dataset_name, candidate_values=original_ids))
    documents = [document for document in documents if document['_texta_id'] in new_ids]
    for document in documents:
        del document['_texta_id']

    processed_documents = list(DocumentProcessor(subprocessors=[]).process(documents=documents))
    storer = DocumentStorer.get_storer(**parameter_dict)
    stored_documents_count = storer.store(processed_documents)
    if processed_documents:
        with lock:
            dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
            dataset_import.processed_documents += stored_documents_count
            dataset_import.save()

            index.add(dataset=dataset_name, values=new_ids)


def _run_processing_jobs(parameter_dict, reader, n_processes, process_batch_size):
    import_job_lock = Lock()

    process_pool = Pool(processes=n_processes, initializer=_init_pool,
                        initargs=(import_job_lock,))

    batch = []

    for document in reader.read_documents(**parameter_dict):
        batch.append(document)

        if len(batch) == process_batch_size:
            process_pool.apply(_processing_job, args=(batch, parameter_dict))
            # _processing_job(batch, parameter_dict)
            batch = []

    if batch:
        process_pool.apply(_processing_job, args=(batch, parameter_dict))
        # _processing_job(batch, parameter_dict)

    process_pool.close()
    process_pool.join()

    _complete_import_job(parameter_dict)


def download(url, target_directory, chunk_size=1024):
    response = requests.get(url, stream=True)

    file_name = _derive_file_name(response, url)
    file_path = os.path.join(target_directory, file_name)

    with open(file_path, 'wb') as downloaded_file:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                downloaded_file.write(chunk)

    return file_path


def prepare_import_directory(importer_directory):
    temp_folder_name = str(int(time.time()*1000000))
    temp_folder_path = os.path.join(importer_directory, temp_folder_name)
    os.makedirs(temp_folder_path)

    return temp_folder_path


def tear_down_import_directory(import_directory_path):
    shutil.rmtree(import_directory_path)


def _derive_file_name(response, url):
    file_name = ''

    if 'content-disposition' in response:
        file_names = re.findall('filename=(.*)', response['content-disposition'])

        if file_names:
            file_name = file_names[0].strip('\'" ')

    if not file_name:
        file_name = os.path.basename(url)

    return file_name

