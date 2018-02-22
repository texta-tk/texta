# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from .models import DatasetImport
from dataset_importer.importer import DatasetImporter, entity_reader_map, collection_reader_map, database_reader_map, extractor_map, preprocessor_map
from dataset_importer.syncer.syncer_process import Syncer

from texta.settings import es_url, DATASET_IMPORTER as DATASET_IMPORTER_CONF

from sys import argv

DATASET_IMPORTER = DatasetImporter(es_url=es_url, configuration=DATASET_IMPORTER_CONF,
                                   data_access_object=DatasetImport, file_system_storer=FileSystemStorage)

# Start synchronizer only when it is enabled AND runserver or an alternative has been called via WSGI.
# A.k.a user hasn't called createsuperuser, migrate or makemigrations.
if (DATASET_IMPORTER_CONF['sync']['enabled'] is True and
        len({'createsuperuser', 'migrate', 'makemigrations'} & set(argv)) == 0):
    DATASET_SYNCER = Syncer(dataset_imports=DatasetImport, importer=DATASET_IMPORTER,
                            interval=DATASET_IMPORTER_CONF['sync']['interval_in_seconds'])
    DATASET_SYNCER.start()


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)

    return entries


@login_required
def index(request):
    jobs = DatasetImport.objects.all()

    archive_formats = collect_map_entries(extractor_map)
    single_document_formats = collect_map_entries(entity_reader_map)
    document_collection_formats = collect_map_entries(collection_reader_map)
    database_formats = collect_map_entries(database_reader_map)

    preprocessors = collect_map_entries(preprocessor_map)

    enabled_preprocessors = [preprocessor for preprocessor in preprocessors]

    return render(request, 'dataset_importer.html', context={
        # 'enabled_input_types': DATASET_IMPORTER_CONF['enabled_input_types'],
        'archive_formats': archive_formats,
        'single_document_formats': single_document_formats,
        'document_collection_formats': document_collection_formats,
        'database_formats': database_formats,
        'jobs': jobs,
        'enabled_preprocessors': enabled_preprocessors
    })


@login_required
def reload_table(request):
    jobs = DatasetImport.objects.all()

    return render(request, 'import_jobs_table.html',
                  context={'jobs': jobs})


@login_required
def import_dataset(request):
    DATASET_IMPORTER.import_dataset(request=request)

    return HttpResponse()


@login_required
def cancel_import_job(request):
    DATASET_IMPORTER.cancel_import_job(request.POST.get('id', ''))

    return HttpResponse()


@login_required
def remove_import_job(request):
    import_id = request.POST.get('id', None)
    if import_id:
        DatasetImport.objects.get(pk=import_id).delete()

    return HttpResponse()
