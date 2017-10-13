# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import os

from django.shortcuts import render

from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from multiprocessing import Process

from utils import download, prepare_import_directory
from archive_extractor.extractor import ArchiveExtractor
from document_reader.reader import DocumentReader
from texta.settings import BASE_DIR

IMPORTER_DIRECTORY = 'test_dir'
IMPORTER_DIRECTORY = os.path.join(os.path.abspath(os.path.join(BASE_DIR, os.pardir)), 'data',IMPORTER_DIRECTORY)

import os
if not os.path.exists(IMPORTER_DIRECTORY):
    os.makedirs(IMPORTER_DIRECTORY)


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

    parameters = json.loads(request.POST['parameters'])

    parameters['directory'] = prepare_import_directory(IMPORTER_DIRECTORY)

    if parameters['format'] not in {'postgres', 'mongodb', 'elastic'}:
        if 'file' in request.FILES:
            fs = FileSystemStorage(location=parameters['directory'])
            file_name = fs.save(request.FILES['file'])
            parameters['file_path'] = fs.path(file_name)
        elif 'url' not in parameters:
            return HttpResponse('failed')

    Process(target=_import_dataset, args=(parameters,)).start()

    HttpResponse()


def _import_dataset(parameter_dict):

    if 'file_path' not in parameter_dict:
        parameter_dict['file_path'] = download(parameter_dict['url'], parameter_dict['directory'])

    if 'archive' in parameter_dict:
        ArchiveExtractor.extract_archive(file_path=parameter_dict['file_path'], archive_format=parameter_dict['archive'])

    DocumentReader(directory=parameter_dict['directory']).read_documents(parameter_dict['format'], **parameter_dict)
