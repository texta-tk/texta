# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import shutil

from django.shortcuts import render

from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from multiprocessing import Process, Pool

from utils import download, prepare_import_directory
from archive_extractor.extractor import ArchiveExtractor
from document_reader.reader import DocumentReader
from document_processor.processor import DocumentProcessor
from document_storer.storer import DocumentStorer

from texta.settings import es_url

PROCESSES = 2
BATCH_SIZE = 1000

def index(request):

    enabled_input_types = {
        'single': [
            {'name': 'Word document', 'value': 'doc'},
            {'name': 'HTML', 'value': 'html'},
            {'name': 'RTF', 'value': 'rtf'},
            {'name': 'PDF', 'value': 'pdf'},
            {'name': 'TXT', 'value': 'txt'},
        ],
        'collection': [
            {'name': 'CSV', 'value': 'csv'},
            {'name': 'JSON', 'value': 'json'},
            {'name': 'Excel spreadsheet', 'value': 'xls'},
            {'name': 'XML', 'value': 'xml'},
        ],
        'database': [
            {'name': 'Elasticsearch', 'value': 'elastic'},
            {'name': 'MongoDB', 'value': 'mongodb'},
            {'name': 'PostgreSQL', 'value': 'postgres'},
            {'name': 'SQLite', 'value': 'sqlite'},
        ]

    }

    return render(request, 'dataset_importer.html', context={'enabled_input_types': enabled_input_types})

def import_dataset(request):
    parameters = {key: (value if not isinstance(value, list) else value[0]) for key, value in request.POST.items()}

    parameters['directory'] = prepare_import_directory(IMPORTER_DIRECTORY)
    parameters['elastic_url'] = es_url

    if DocumentStorer.exists(**parameters):
        return HttpResponse('Index and mapping exist', status=403)

    if parameters['format'] not in {'postgres', 'mongodb', 'elastic'}:
        if 'file' in request.FILES:
            fs = FileSystemStorage(location=parameters['directory'])
            file_name = fs.save(request.FILES['file'].name, request.FILES['file'])
            parameters['file_path'] = fs.path(file_name)
        elif 'url' not in parameters:
            return HttpResponse('failed')

    Process(target=_import_dataset, args=(parameters,)).start()

    return HttpResponse()


def _import_dataset(parameter_dict):

    if 'file_path' not in parameter_dict:
        parameter_dict['file_path'] = download(parameter_dict['url'], parameter_dict['directory'])

    if 'archive' in parameter_dict:
        ArchiveExtractor.extract_archive(file_path=parameter_dict['file_path'], archive_format=parameter_dict['archive'])

    process_pool = Pool(processes=PROCESSES)

    batch = []

    for document in DocumentReader(directory=parameter_dict['directory']).read_documents(**parameter_dict):
        batch.append(document)

        if len(batch) == BATCH_SIZE:
            process_pool.apply(_processing_job, args=(batch, parameter_dict))
            batch = []

    if batch:
        process_pool.apply(_processing_job, args=(batch, parameter_dict))

    process_pool.close()
    process_pool.join()

    shutil.rmtree(parameter_dict['directory'])


def _processing_job(documents, parameter_dict):
    processed_documents = DocumentProcessor(subprocessors=[]).process(documents=documents)
    storer = DocumentStorer.get_storer(**parameter_dict)
    storer.store(processed_documents)
