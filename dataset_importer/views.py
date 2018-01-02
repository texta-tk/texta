# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from .models import DatasetImport
from dataset_importer.importer import DatasetImporter
from dataset_importer.syncer.syncer_process import Syncer

from texta.settings import es_url, DATASET_IMPORTER as DATASET_IMPORTER_CONF

ACTIVE_IMPORT_JOBS = {}

DATASET_IMPORTER = DatasetImporter(es_url=es_url, configuration=DATASET_IMPORTER_CONF,
                                   data_access_object=DatasetImport, file_system_storer=FileSystemStorage)
DATASET_SYNCER = Syncer(dataset_imports=DatasetImport, importer=DATASET_IMPORTER,
                        interval=DATASET_IMPORTER_CONF['sync']['interval_in_seconds'])
DATASET_SYNCER.start()


def index(request):
    jobs = DatasetImport.objects.all()

    return render(request, 'dataset_importer.html',
                  context={'enabled_input_types': DATASET_IMPORTER_CONF['enabled_input_types'], 'jobs': jobs})


def reload_table(request):
    jobs = DatasetImport.objects.all()

    return render(request, 'import_jobs_table.html',
                  context={'jobs': jobs})


def import_dataset(request):
    DATASET_IMPORTER.import_dataset(request=request)

    return HttpResponse()


def cancel_import_job(request):
    DATASET_IMPORTER.cancel_import_job(request.POST.get('id', ''))

    return HttpResponse()


def remove_import_job(request):
    import_id = request.POST.get('id', None)
    if import_id:
        DatasetImport.objects.get(pk=import_id).delete()

    return HttpResponse()
