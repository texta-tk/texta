from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit import pagination
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query

from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tagger.tasks import train_tagger
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import TaggerSerializer, TaggerGroupSerializer, \
                                       TextSerializer, DocSerializer, \
                                       TextGroupSerializer, DocGroupSerializer, \
                                       FeatureListSerializer
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.model_cache import ModelCache
from toolkit.embedding.phraser import Phraser
from toolkit.tools.text_processor import TextProcessor
from toolkit import permissions as toolkit_permissions
from toolkit.view_constants import TagLogicViews
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.core.task.models import Task

import json

# initialize model cache for taggers & phrasers
model_cache = ModelCache(TextTagger)
phraser_cache = ModelCache(Phraser)


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:
        data = request.POST
    else:
        data = {}
    return data


class TaggerViewSet(viewsets.ModelViewSet):
    serializer_class = TaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']))


    def get_queryset(self):
        return Tagger.objects.filter(project=self.kwargs['project_pk'])


    def create(self, request, *args, **kwargs):
        serializer = TaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)



    @action(detail=True, methods=['get', 'post'], serializer_class=FeatureListSerializer)
    def list_features(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger features.
        """
        data = get_payload(request)
        serializer = FeatureListSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve model
        tagger = model_cache.get_model(tagger_object.pk)

        try:
            # get feature names
            features = tagger.get_feature_names()
        except:
            return Response({'error': 'Error loading feature names. Are you using HashingVectorizer? It does not support feature names!'}, status=status.HTTP_400_BAD_REQUEST)

        feature_coefs = tagger.get_feature_coefs()
        supports = tagger.get_supports()
        selected_features = [feature for i, feature in enumerate(features) if supports[i]]
        selected_features = [{'feature': feature, 'coefficient': feature_coefs[i]} for i, feature in enumerate(selected_features) if feature_coefs[i] > 0]
        selected_features = sorted(selected_features, key=lambda k: k['coefficient'], reverse=True)

        features_to_show = selected_features[:serializer.validated_data['size']]
        feature_info = {'features': features_to_show,
                        'total_features': len(selected_features),
                        'showing_features': len(features_to_show)}
        return Response(feature_info, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def stop_word_list(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger object stop words.
        """
        # retrieve tagger object and load stop words
        tagger_object = self.get_object()
        success = {'stop_words': json.loads(tagger_object.stop_words)}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def stop_word_add(self, request, pk=None, project_pk=None):
        """
        API endpoint for adding a new stop word to tagger
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        new_stop_word = serializer.validated_data['text']

        # retrieve tagger object and update stop word list
        tagger_object = self.get_object()
        stop_words = json.loads(tagger_object.stop_words)
        if new_stop_word not in stop_words:
            stop_words.append(new_stop_word)

        # save tagger object
        tagger_object.stop_words = json.dumps(stop_words)
        tagger_object.save()

        success = {'added': new_stop_word, 'stop_words': stop_words}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def stop_word_remove(self, request, pk=None, project_pk=None):
        """
        API endpoint for removing tagger stop word.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        remove_stop_word = serializer.validated_data['text']

        # retrieve tagger object and update stop word list
        tagger_object = self.get_object()
        stop_words = json.loads(tagger_object.stop_words)

        # check is word in list
        if remove_stop_word not in stop_words:
            return Response({'error': 'word not present among stop words'}, status=status.HTTP_400_BAD_REQUEST)

        # remove stop word
        stop_words.remove(remove_stop_word)

        # save tagger object
        tagger_object.stop_words = json.dumps(stop_words)
        tagger_object.save()

        success = {'removed': remove_stop_word, 'stop_words': stop_words}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """
        API endpoint for retraining tagger model.
        """
        instance = self.get_object()
        train_tagger.apply_async(args=(instance.pk,))
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=TextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging raw text.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # create text processor object for tagger
        stop_words = json.loads(tagger_object.stop_words)
        if tagger_object.embedding:
            phraser = phraser_cache.get_model(tagger_object.embedding.pk)
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.validated_data['text'], input_type='text', text_processor=text_processor)
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=DocSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging JSON documents.
        """
        data = get_payload(request)
        serializer = DocSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # check if fields match
        field_path_list = json.loads(tagger_object.fields)
        if set(field_path_list) != set(serializer.validated_data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(field_path_list)}, status=status.HTTP_400_BAD_REQUEST)

        # create text processor object for tagger
        stop_words = json.loads(tagger_object.stop_words)
        if tagger_object.embedding:
            phraser = phraser_cache.get_model(tagger_object.embedding.pk)
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.validated_data['doc'], input_type='doc', text_processor=text_processor)
        return Response(tagger_response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_id, tagger_input, input_type='text', text_processor=None):
        tagger = model_cache.get_model(tagger_id)
        tagger.add_text_processor(text_processor)

        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        return {'result': bool(tagger_result[0]), 'probability': tagger_result[1]}


################
# TAGGER GROUP #
################


class TaggerGroupViewSet(viewsets.ModelViewSet, TagLogicViews):
    queryset = TaggerGroup.objects.all()
    serializer_class = TaggerGroupSerializer
    pagination_class = pagination.TaggerGroupsPagination
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


    def get_tag_candidates(self, field_paths, text, hybrid=True, n_candidates=30):
        """
        Finds frequent tags from documents similar to input document.
        Returns empty list if hybrid option false.
        """
        if not hybrid:
            return []

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
            train_tagger.apply_async(args=(tagger.pk,))
        return Response({'success': 'retraining tasks created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def models_load(self, request, pk=None, project_pk=None):
        """
        API endpoint for loading all relevant tagger models.
        """
        num_phrasers = 0
        num_taggers = 0
        instance = self.get_object()
        for tagger in instance.taggers.all():
            # load tagger model
            model_cache.get_model(tagger.pk)
            num_taggers += 1
            if tagger.embedding:
                # load phraser model
                phraser_cache.get_model(tagger.embedding.pk)
                num_phrasers += 1
        return Response({'loaded': {'phraser': num_phrasers, 'tagger': num_taggers}}, status=status.HTTP_200_OK)


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
            return Response({'error': 'models doe not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve field data from the first element
        # we can do that safely because all taggers inside
        # hybrid tagger instance are trained on same fields
        hybrid_tagger_field_data = json.loads(hybrid_tagger_object.taggers.first().fields)

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(hybrid_tagger_field_data,
                                                 serializer.validated_data['text'],
                                                 hybrid=serializer.validated_data['hybrid'],
                                                 n_candidates=serializer.validated_data['num_candidates'])

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, serializer.validated_data['text'], input_type='text', show_candidates=serializer.validated_data['show_candidates'])

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

        # check if fields match
        if set(hybrid_tagger_field_data) != set(serializer.validated_data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(hybrid_tagger_field_data)}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tag candidates
        combined_texts = ' '.join(serializer.validated_data['doc'].values())
        tag_candidates = self.get_tag_candidates(hybrid_tagger_field_data,
                                                 combined_texts,
                                                 n_candidates=serializer.validated_data['num_candidates'])

        # get tags
        tags = self.apply_taggers(hybrid_tagger_object, tag_candidates, serializer.validated_data['doc'], input_type='doc', show_candidates=serializer.validated_data['show_candidates'])
        return Response(tags, status=status.HTTP_200_OK)


    def apply_taggers(self, hybrid_tagger_object, tag_candidates, tagger_input, input_type='text', show_candidates=False):
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
                text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
            else:
                text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

            # load tagger model
            tagger = model_cache.get_model(tagger_id)
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
