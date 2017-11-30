# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import shutil
from datetime import datetime
import os

from django.shortcuts import render

from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from multiprocessing import Process, Pool, Lock

from utils import download, prepare_import_directory
from archive_extractor.extractor import ArchiveExtractor
from document_reader.reader import DocumentReader
from document_processor.processor import DocumentProcessor
from document_storer.storer import DocumentStorer
from .models import DatasetImport

from texta.settings import es_url, DATASET_IMPORTER

ACTIVE_IMPORT_JOBS = {}


def index(request):
    jobs = DatasetImport.objects.all()

    return render(request, 'dataset_importer.html',
                  context={'enabled_input_types': DATASET_IMPORTER['enabled_input_types'], 'jobs': jobs})


def reload_table(request):
    jobs = DatasetImport.objects.all()

    return render(request, 'import_jobs_table.html',
                  context={'jobs': jobs})


def import_dataset(request):
    parameters = {key: (value if not isinstance(value, list) else value[0]) for key, value in request.POST.items()}

    parameters['directory'] = prepare_import_directory(DATASET_IMPORTER['directory'])
    parameters['elastic_url'] = es_url

    # if DocumentStorer.exists(**parameters):  # TODO remove in order to allow to add more documents to an existing index
    #     return HttpResponse('Index and mapping exist', status=403)

    if parameters['format'] not in {'postgres', 'mongodb', 'elastic'}:
        if 'file' in request.FILES:
            fs = FileSystemStorage(location=parameters['directory'])
            file_name = fs.save(request.FILES['file'].name, request.FILES['file'])
            parameters['file_path'] = fs.path(file_name)
        elif 'url' not in parameters:
            return HttpResponse('failed')

    dataset_import = DatasetImport.objects.create(
        source_type=_get_source_type(parameters.get('format', ''), parameters.get('archive', '')),
        source_name=_get_source_name(parameters),
        elastic_index=parameters.get('elastic_index', ''), elastic_mapping=parameters.get('elastic_mapping', ''),
        start_time=datetime.now(), end_time=None, user=request.user, status='Processing', finished=False
    )
    dataset_import.save()
    parameters['import_id'] = dataset_import.pk

    #process = Process(target=_import_dataset, args=(parameters, processed_docs_value)).start()
    process = None
    _import_dataset(parameters)

    ACTIVE_IMPORT_JOBS[dataset_import.pk] = {
        'process': process,
        'parameters': parameters
    }

    return HttpResponse()


def cancel_import_job(request):
    import_id = request.POST.get('id', '')

    import_dict = ACTIVE_IMPORT_JOBS.get(int(import_id), None)

    if import_dict:
        import_process = import_dict.get('process', None)
        if import_process:
            import_process.terminate()

        shutil.rmtree(import_dict['directory'])

    try:
        dataset_import = DatasetImport.objects.get(pk=import_id)
        dataset_import.finished = True
        dataset_import.status = 'Cancelled'
        dataset_import.save()
    except:
        pass

    return HttpResponse()


def remove_import_job(request):
    import_id = request.POST.get('id', None)
    if import_id:
        DatasetImport.objects.get(pk=import_id).delete()

    return HttpResponse()


def _get_active_import_jobs():
    import_jobs = DatasetImport.objects.filter(finished=False).order_by('-start_time')
    processed_import_jobs = []

    for import_job in import_jobs:
        processed_import_jobs.append({
            'id': import_job.pk,
            'source_type': import_job.source_type,
            'source_name': import_job.source_name,
            'elastic_index': import_job.elastic_index,
            'elastic_mapping': import_job.elastic_mapping,
            'start_time': import_job.start_time,
            'end_time': import_job.end_time,
            'user': import_job.user.username,
            'status': 'Processing [{0}%]'.format(
                int(import_job.processed_documents / import_job.total_documents) * 100),
            'total_documents': import_job.total_documents
        })

    return processed_import_jobs


def _get_historic_import_jobs():
    return DatasetImport.objects.filter(finished=True).order_by('-start_time', '-end_time')


def _get_source_type(format, archive):
    source_type_parts = [format]
    if archive:
        source_type_parts.append('|')
        source_type_parts.append(archive)

    return ''.join(source_type_parts)


def _get_source_name(parameters):
    if 'file_path' in parameters:
        return os.path.basename(parameters['file_path'])
    elif 'url' in parameters:
        return parameters['url']
    else:
        return ''


def _import_dataset(parameter_dict):
    if 'file_path' not in parameter_dict:
        parameter_dict['file_path'] = download(parameter_dict['url'], parameter_dict['directory'])

    if 'archive' in parameter_dict:
        ArchiveExtractor.extract_archive(file_path=parameter_dict['file_path'], archive_format=parameter_dict['archive'])

    reader = DocumentReader(directory=parameter_dict['directory'])
    dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
    dataset_import.total_documents = reader.count_total_documents(**parameter_dict)
    dataset_import.save()

    import_job_lock = Lock()

    process_pool = Pool(processes=DATASET_IMPORTER['import_processes'], initializer=_init_pool, initargs=(import_job_lock,))

    batch = []

    for document in reader.read_documents(**parameter_dict):
        batch.append(document)

        if len(batch) == DATASET_IMPORTER['process_batch_size']:
            process_pool.apply(_processing_job, args=(batch, parameter_dict))
            batch = []

    if batch:
        process_pool.apply(_processing_job, args=(batch, parameter_dict))

    process_pool.close()
    process_pool.join()

    dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
    dataset_import.end_time = datetime.now()
    dataset_import.status = 'Completed'
    dataset_import.save()

    shutil.rmtree(parameter_dict['directory'])


def _init_pool(lock_):
    global lock
    lock = lock_


def _processing_job(documents, parameter_dict):
    processed_documents = DocumentProcessor(subprocessors=[]).process(documents=documents)
    storer = DocumentStorer.get_storer(**parameter_dict)
    stored_documents_count = storer.store(processed_documents)

    with lock:
        dataset_import = DatasetImport.objects.get(pk=parameter_dict['import_id'])
        dataset_import.processed_documents += stored_documents_count
        dataset_import.save()
