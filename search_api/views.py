# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import

from django.http import HttpResponse, StreamingHttpResponse
import json

from .processors.rest_processor import RestProcessor, Validator
from .elastic.aggregator import Aggregator
from .elastic.searcher import Searcher
from .elastic.listing import ElasticListing

from texta.settings import es_url, date_format
from permission_admin.models import Dataset


def search(request):
    try:
        processed_request = RestProcessor().process_searcher(request)
    except Exception as processing_error:
        return StreamingHttpResponse([json.dumps({'error': str(processing_error)})])

    results = Searcher(es_url).search(processed_request)
    return StreamingHttpResponse(process_stream(results), content_type='application/json')


def scroll(request):
    try:
        processed_request = RestProcessor().process_searcher(request)
    except Exception as processing_error:
        return HttpResponse(json.dumps({'error': str(processing_error)}))

    results = Searcher(es_url).scroll(processed_request)

    return HttpResponse(json.dumps(results, ensure_ascii=False))


def aggregate(request):
    try:
        processed_request = RestProcessor().process_aggregator(request)
    except Exception as processing_error:
        return HttpResponse(json.dumps({'error': str(processing_error)}))

    results = Aggregator(date_format, es_url).aggregate(processed_request)

    return HttpResponse(json.dumps(results, ensure_ascii=False))


def list_datasets(request):
    try:
        user = Validator.get_validated_user(request)
    except Exception as validation_error:
        return HttpResponse(json.dumps({'error': str(validation_error)}))

    listing = ElasticListing(es_url)
    registered_datasets = Dataset.objects.all()
    existing_datasets = listing.get_available_datasets(registered_datasets, user)

    return HttpResponse('\n'.join([json.dumps(existing_dataset) for existing_dataset in existing_datasets]), content_type='application/json')


def list_fields(request):
    try:
        user = Validator.get_validated_user(request)
    except Exception as validation_error:
        return HttpResponse(json.dumps({'error': str(validation_error)}))

    request_body = json.loads(request.body.decode('utf8'))
    if 'dataset' not in request_body:
        return HttpResponse(json.dumps({'error': 'Dataset not defined.'}))

    dataset_id = request_body['dataset']

    try:
        dataset = Dataset.objects.get(pk=dataset_id)
    except:
        return HttpResponse(json.dumps({'error': 'Dataset ID is not matching any datasets.'}))

    if not user.has_perm('permission_admin.can_access_dataset_{0}'.format(dataset_id)):
        return HttpResponse(json.dumps({'error': 'No permission to query dataset {0}'.format(dataset_id)}))

    listing = ElasticListing(es_url)
    properties = listing.get_dataset_properties(dataset)

    return HttpResponse(json.dumps(properties), content_type='application/json')


def process_stream(generator):
    for entry in generator:
        new_entry = {}
        for key in entry:
            new_entry[key] = entry[key]

        yield json.dumps(new_entry, ensure_ascii=False)
        yield '\n'