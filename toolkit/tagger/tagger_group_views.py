import json
import re
import sys

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query

from toolkit.tagger.tasks import train_tagger
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import TaggerGroupSerializer, TextGroupSerializer, DocGroupSerializer
from toolkit.tools.text_processor import TextProcessor
from toolkit.view_constants import TagLogicViews
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.core.task.models import Task
from toolkit.tools.mlp_lemmatizer import MLPLemmatizer
from toolkit.helper_functions import apply_celery_task, get_payload
from toolkit.tagger.validators import validate_input_document

from toolkit.embedding.views import phraser_cache
from toolkit.tagger.tagger_views import tagger_cache


class TaggerGroupViewSet(viewsets.ModelViewSet, TagLogicViews):
    queryset = TaggerGroup.objects.all()
    serializer_class = TaggerGroupSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
        )

    def perform_create(self, serializer, tagger_set):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        taggers=tagger_set)


    def get_queryset(self):
        return TaggerGroup.objects.filter(project=self.kwargs['project_pk'])


    def create(self, request, *args, **kwargs):
        # add dummy value to tagger so serializer is happy
        request_data = request.data.copy()
        request_data.update({'tagger.description': 'dummy value'})

        # validate serializer again with updated values
        serializer = TaggerGroupSerializer(data=request_data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        fact_name = serializer.validated_data['fact_name']
        active_project = Project.objects.get(id=self.kwargs['project_pk'])

        # retrieve tags with sufficient counts & create queries to build models
        tags = self.get_tags(fact_name, active_project, min_count=serializer.validated_data['minimum_sample_size'])

        # check if found any tags to build models on
        if not tags:
            return Response({'error': f'found no tags for fact name: {fact_name}'}, status=status.HTTP_400_BAD_REQUEST)


        tag_queries = self.create_queries(fact_name, tags)

        # retrive tagger options from hybrid tagger serializer
        validated_tagger_data = serializer.validated_data.pop('tagger')
        validated_tagger_data.update('')

        # create tagger objects
        tagger_set = set()
        for i,tag in enumerate(tags):
            tagger_data = validated_tagger_data.copy()
            tagger_data.update({'query': json.dumps(tag_queries[i])})
            tagger_data.update({'description': tag})
            tagger_data.update({'fields': json.dumps(tagger_data['fields'])})
            created_tagger = Tagger.objects.create(**tagger_data,
                                      author=request.user,
                                      project=active_project)
            tagger_set.add(created_tagger)

        # create hybrid tagger object
        self.perform_create(serializer, tagger_set)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def get_tag_candidates(self, field_paths, text, n_candidates=30):
        """
        Finds frequent tags from documents similar to input document.
        Returns empty list if hybrid option false.
        """
        # create es aggregator object
        es_a = ElasticAggregator()
        es_a.update_field_data(field_paths)

        # process text
        text = TextProcessor(remove_stop_words=True).process(text)[0]

        # create & update query
        query = Query()
        query.add_mlt(field_paths, text)
        es_a.update_query(query.query)

        # perform aggregation to find frequent tags
        tag_candidates = es_a.facts(filter_by_fact_name=self.get_object().fact_name, size=n_candidates)
        return tag_candidates


    @action(detail=True, methods=['get', 'post'])
    def models_list(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger objects connected to tagger group instance.
        """
        path = re.sub(r'tagger_groups/\d+/models_list/*$', 'taggers/', request.path)
        tagger_url_prefix = request.build_absolute_uri(path)
        tagger_objects = TaggerGroup.objects.get(id=pk).taggers.all()
        response = [{'tag': tagger.description, 'id': tagger.id, 'url': f'{tagger_url_prefix}{tagger.id}/', 'status': tagger.task.status} for tagger in tagger_objects]

        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def models_retrain(self, request, pk=None, project_pk=None):
        """
        API endpoint for retraining tagger model.
        """
        instance = self.get_object()
        # start retraining tasks
        for tagger in instance.taggers.all():
            # update task status so statistics are correct during retraining
            tagger.status = Task.STATUS_CREATED
            tagger.save()
            apply_celery_task(train_tagger, tagger.pk)

        return Response({'success': 'retraining tasks created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging a random document.
        """
        # get hybrid tagger object
        hybrid_tagger_object = self.get_object()
        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status=Task.STATUS_COMPLETED):
            return Response({'error': 'models do not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger fields from the first object
        tagger_fields = json.loads(hybrid_tagger_object.taggers.first().fields)

        if not ElasticCore().check_if_indices_exist(hybrid_tagger_object.project.indices):
            return Response({'error': f'One or more index from {list(hybrid_tagger_object.project.indices)} do not exist'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve random document
        random_doc = ElasticSearcher(indices=hybrid_tagger_object.project.indices).random_documents(size=1)[0]
        # filter out correct fields from the document
        random_doc_filtered = {k:v for k,v in random_doc.items() if k in tagger_fields}
        # combine document field values into one string
        combined_texts = '\n'.join(random_doc_filtered.values())
        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(tagger_fields, combined_texts)
        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, random_doc_filtered, input_type='doc')
        # return document with tags
        response = {"document": random_doc, "tags": tags}
        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=TextGroupSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging raw text with tagger group.
        """
        data = get_payload(request)
        serializer = TextGroupSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        hybrid_tagger_object = self.get_object()

        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status=Task.STATUS_COMPLETED):
            return Response({'error': 'models do not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve field data from the first element
        # we can do that safely because all taggers inside
        # hybrid tagger instance are trained on same fields
        hybrid_tagger_field_data = json.loads(hybrid_tagger_object.taggers.first().fields)

        # declare text variable
        text = serializer.validated_data['text']

        # by default, lemmatizer is disabled
        lemmatizer = False

        # lemmatize if needed
        if serializer.validated_data['lemmatize'] == True:
            lemmatizer = MLPLemmatizer(lite=True)
            # check if lemmatization available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # lemmatize text
            text = lemmatizer.lemmatize(text)
            # check if any non stop words left
            if not text:
                return Response({'error': 'no words left after lemmatization. did your request contain only stop words?'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(hybrid_tagger_field_data,
                                                 text,
                                                 n_candidates=serializer.validated_data['num_candidates'])

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, text, input_type='text', show_candidates=serializer.validated_data['show_candidates'])

        return Response(tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=DocGroupSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging JSON documents with tagger group.
        """
        data = get_payload(request)
        serializer = DocGroupSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        hybrid_tagger_object = self.get_object()

        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status=Task.STATUS_COMPLETED):
            return Response({'error': 'models doe not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve field data from the first element
        # we can do that safely because all taggers inside
        # hybrid tagger instance are trained on same fields
        hybrid_tagger_field_data = json.loads(hybrid_tagger_object.taggers.first().fields)

        # declare input_document variable
        input_document = serializer.validated_data['doc']

        # validate input document
        input_document, error_response = validate_input_document(input_document, hybrid_tagger_field_data)
        if error_response:
            return error_response

        # combine document field values into one string
        combined_texts = '\n'.join(input_document.values())

        # by default, lemmatizer is disabled
        lemmatizer = False

        # lemmatize if needed
        if serializer.validated_data['lemmatize'] == True:
            lemmatizer = MLPLemmatizer(lite=True)
            # check if lemmatization available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # lemmatize text
            combined_texts = lemmatizer.lemmatize(combined_texts)
            # check if any non stop words left
            if not combined_texts:
                return Response({'error': 'no words left after lemmatization. did your request contain only stop words?'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(hybrid_tagger_field_data,
                                                 combined_texts,
                                                 n_candidates=serializer.validated_data['num_candidates'])

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object,
                                  tag_candidates,
                                  serializer.validated_data['doc'],
                                  input_type='doc',
                                  show_candidates=serializer.validated_data['show_candidates'],
                                  lemmatizer=lemmatizer)
        return Response(tags, status=status.HTTP_200_OK)


    def apply_taggers(self, hybrid_tagger_object, tag_candidates, tagger_input, input_type='text', show_candidates=False, lemmatizer=None):
        # filter if tag candidates. use all if no candidates.
        if tag_candidates:
            tagger_objects = hybrid_tagger_object.taggers.filter(description__in=tag_candidates)
        else:
            tagger_objects = hybrid_tagger_object.taggers.all()
        tags = []

        for tagger in tagger_objects:
            tagger_id = tagger.pk

            # create text processor object for tagger
            stop_words = json.loads(tagger.stop_words)
            if tagger.embedding:
                phraser = phraser_cache.get_model(tagger.embedding.pk)
                text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
            else:
                text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)

            # load tagger model
            tagger = tagger_cache.get_model(tagger_id)
            if tagger:
                tagger.add_text_processor(text_processor)
                if input_type == 'doc':
                    tagger_result = tagger.tag_doc(tagger_input)
                else:
                    tagger_result = tagger.tag_text(tagger_input)
                decision = bool(tagger_result[0])
                tagger_response = {'tag': tagger.description, 'probability': tagger_result[1], 'tagger_id': tagger_id}

                if not show_candidates and decision:
                    # filter tags if omitted
                    tags.append(tagger_response)
                elif show_candidates:
                    # show tag candidates if asked
                    tagger_response['decision'] = decision
                    tags.append(tagger_response)

        return sorted(tags, key=lambda k: k['probability'], reverse=True)
