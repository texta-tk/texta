# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse, StreamingHttpResponse
import json

from processors.rest_processor import  RestProcessor
from elastic.aggregator import Aggregator
from elastic.searcher import Searcher
from elastic.listing import ElasticListing

from texta.settings import es_url
from permission_admin.models import Dataset

def search(request):
    processed_request = RestProcessor().process(request)
    results = Searcher(es_url).search(processed_request)

    return StreamingHttpResponse(process_stream(results), content_type='application/json')


def aggregate(request):
    processed_request = RestProcessor().process(request)
    results = Aggregator(request).aggregate(processed_request)

    return StreamingHttpResponse(results)


def list_datasets(request):
    listing = ElasticListing(es_url)
    registered_datasets = Dataset.objects.all()
    existing_datasets = listing.get_existing_datasets(registered_datasets)

    return HttpResponse('\n'.join([json.dumps(existing_dataset) for existing_dataset in existing_datasets]), content_type='application/json')


def list_fields(request, dataset_id):
    listing = ElasticListing(es_url)
    dataset = Dataset.objects.get(pk=dataset_id)
    properties = listing.get_dataset_properties(dataset)

    return HttpResponse(json.dumps(properties))


def process_stream(generator, encoding='utf8'):
    for entry in generator:
        new_entry = {}
        for key in entry:
            new_entry[key] = entry[key]
            # if key == 'texta_facts':
            #     new_entry[key] = entry[key]
            # else:
            #     new_entry[key.encode('utf8')] = entry[key].encode(encoding)

        yield json.dumps(new_entry)
        yield '\n'