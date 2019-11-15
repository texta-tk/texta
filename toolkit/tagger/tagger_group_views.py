import os
import json
import re
import sys
from celery import group

from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query

from toolkit.tagger.tasks import train_tagger, apply_tagger, create_tagger_objects
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import TaggerGroupSerializer, TaggerGroupTagTextSerializer, TaggerGroupTagDocumentSerializer
from toolkit.tools.text_processor import TextProcessor
from toolkit.view_constants import TagLogicViews, BulkDelete
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.core.task.models import Task
from toolkit.helper_functions import apply_celery_task
from toolkit.tagger.validators import validate_input_document
from toolkit.tagger.tagger_views import global_mlp_for_taggers



class TaggerGroupViewSet(mixins.CreateModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.DestroyModelMixin,
                         viewsets.GenericViewSet,
                         TagLogicViews,
                         BulkDelete):

    queryset = TaggerGroup.objects.all()
    serializer_class = TaggerGroupSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
        )


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

        # create queries for taggers
        tag_queries = self.create_queries(fact_name, tags)

        # retrive tagger options from hybrid tagger serializer
        validated_tagger_data = serializer.validated_data.pop('tagger')
        validated_tagger_data.update('')

        # create tagger group object
        tagger_group = serializer.save(author=self.request.user,
                                       project=Project.objects.get(id=self.kwargs['project_pk']),
                                       num_tags=len(tags)
                                       )

        # create taggers objects inside tagger group object
        # use async to make things faster
        apply_celery_task(create_tagger_objects, tagger_group.pk, validated_tagger_data, tags, tag_queries)

        # retrieve headers and create response
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        tagger_objects = instance.taggers.all()
        for tagger in tagger_objects:
            self.perform_destroy(tagger)
        self.perform_destroy(instance)
        tagger_model_locations = [json.loads(tagger.location)['tagger'] for tagger in tagger_objects]
        tagger_plot_locations = [tagger.plot.path for tagger in tagger_objects]
        try:
            for model_dir_list in (
                        tagger_model_locations,
                        tagger_plot_locations,
                        ):
                for model_dir in model_dir_list:
                    os.remove(model_dir)
            return Response({"success": "Taggergroup instance deleted, related tagger instances deleted and related models and plots removed"}, status=status.HTTP_204_NO_CONTENT)
        except:
            return Response({"success": "Taggergroup instance deleted, related tagger instances deleted, but related models and plots were not removed"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['get'])
    def models_list(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger objects connected to tagger group instance.
        """
        path = re.sub(r'tagger_groups/\d+/models_list/*$', 'taggers/', request.path)
        tagger_url_prefix = request.build_absolute_uri(path)
        tagger_objects = TaggerGroup.objects.get(id=pk).taggers.all()
        response = [{'tag': tagger.description, 'id': tagger.id, 'url': f'{tagger_url_prefix}{tagger.id}/', 'status': tagger.task.status} for tagger in tagger_objects]

        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
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
        return Response({'success': 'retraining tasks created', 'tagger_group_id': instance.id}, status=status.HTTP_200_OK)


    def get_mlp(self, text, lemmatize=False, use_ner=True):
        """
        Retrieves lemmas.
        Retrieves tags predicted by MLP NER and present in models.
        :return: string, list
        """
        tags = []
        hybrid_tagger_object = self.get_object()
        taggers = {t.description.lower(): {"tag": t.description, "id": t.id} for t in hybrid_tagger_object.taggers.all()}
        mlp_output = global_mlp_for_taggers.process(text)
        # lemmatize
        if lemmatize and mlp_output:
            text = mlp_output["text"]["lemmas"]
        # retrieve tags
        if use_ner and mlp_output:
            seen_tags = {}
            for fact in mlp_output["texta_facts"]:
                fact_val = fact["str_val"].lower().strip()
                if fact_val in taggers and fact_val not in seen_tags:
                    fact_val_dict = {
                        "tag": taggers[fact_val]["tag"],
                        "probability": 1.0,
                        "tagger_id": taggers[fact_val]["id"],
                        "ner_match": True
                    }
                    tags.append(fact_val_dict)
                    seen_tags[fact_val] = True
        return text, tags


    def get_tag_candidates(self, text, ignore_tags=[], n_similar_docs=10, max_candidates=10):
        """
        Finds frequent tags from documents similar to input document.
        Returns empty list if hybrid option false.
        """
        hybrid_tagger_object = self.get_object()
        field_paths = json.loads(hybrid_tagger_object.taggers.first().fields)
        indices = hybrid_tagger_object.project.indices
        ignore_tags = {tag["tag"]: True for tag in ignore_tags}
        # create query
        query = Query()
        query.add_mlt(field_paths, text)
        # create Searcher object for MLT
        es_s = ElasticSearcher(indices=indices, query=query.query)
        docs = es_s.search(size=n_similar_docs)
        # dict for tag candidates from elastic
        tag_candidates = {}
        # retrieve tags from elastic response
        for doc in docs:
            if "texta_facts" in doc:
                for fact in doc["texta_facts"]:
                    if fact["fact"] == hybrid_tagger_object.fact_name:
                        fact_val = fact["str_val"]
                        if fact_val not in ignore_tags:
                            if fact_val not in tag_candidates:
                                tag_candidates[fact_val] = 0
                            tag_candidates[fact_val] += 1
        # sort and limit candidates
        tag_candidates = [item[0] for item in sorted(tag_candidates.items(), key=lambda k: k[1], reverse=True)][:max_candidates]
        return tag_candidates


    @action(detail=True, methods=['post'], serializer_class=TaggerGroupTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging raw text with tagger group.
        """
        data = request.data
        serializer = TaggerGroupTagTextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        hybrid_tagger_object = self.get_object()

        # check if any of the models ready
        if not hybrid_tagger_object.taggers.filter(task__status=Task.STATUS_COMPLETED):
            return Response({'error': 'models do not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # declare tag candidates variables
        text = serializer.validated_data['text']
        n_similar_docs = serializer.validated_data['n_similar_docs']
        lemmatize = serializer.validated_data['lemmatize']
        use_ner = serializer.validated_data['use_ner']

        # check if MLP available
        if lemmatize or use_ner:
            if not global_mlp_for_taggers.status:
                return Response({'error': 'mlp not available. check connection to mlp.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # update text and tags with MLP
        text, tags = self.get_mlp(text, lemmatize=lemmatize, use_ner=use_ner)

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(text, ignore_tags=tags, n_similar_docs=n_similar_docs)
        # get tags
        tags += self.apply_tagger_group(text, tag_candidates, input_type='text')
        return Response(tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TaggerGroupTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging JSON documents with tagger group.
        """
        data = request.data
        serializer = TaggerGroupTagDocumentSerializer(data=data)

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

        # declare tag candidates variables
        n_similar_docs = serializer.validated_data['n_similar_docs']
        lemmatize = serializer.validated_data['lemmatize']
        use_ner = serializer.validated_data['use_ner']

        # check if MLP available
        if lemmatize or use_ner:
            if not global_mlp_for_taggers.status:
                return Response({'error': 'mlp not available. check connection to mlp.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # update text and tags with MLP
        combined_texts, tags = self.get_mlp(combined_texts, lemmatize=lemmatize, use_ner=use_ner)

        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(combined_texts, ignore_tags=tags, n_similar_docs=n_similar_docs)
        # get tags
        tags += self.apply_tagger_group(input_document, tag_candidates, input_type='doc', lemmatize=True)
        return Response(tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
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
        combined_texts, tags = self.get_mlp(combined_texts, lemmatize=False)
        # retrieve tag candidates
        tag_candidates = self.get_tag_candidates(combined_texts, ignore_tags=tags)
        # get tags
        tags += self.apply_tagger_group(random_doc_filtered, tag_candidates, input_type='doc')
        # return document with tags
        response = {"document": random_doc, "tags": tags}
        return Response(response, status=status.HTTP_200_OK)


    def apply_tagger_group(self, text, tag_candidates, input_type='text', lemmatize=False):
        # get tagger group object
        tagger_group_object = self.get_object()
        # get tagger objects
        candidates_str = "|".join(tag_candidates)
        tagger_objects = tagger_group_object.taggers.filter(description__iregex=f"^({candidates_str})$")
        # filter out completed
        tagger_objects = [tagger for tagger in tagger_objects if tagger.task.status == tagger.task.STATUS_COMPLETED]
        # predict & sort tags
        tags = group(apply_tagger.s(text, tagger.pk, input_type) for tagger in tagger_objects).apply()
        tags = [tag for tag in tags.get() if tag]
        return sorted(tags, key=lambda k: k['probability'], reverse=True)
