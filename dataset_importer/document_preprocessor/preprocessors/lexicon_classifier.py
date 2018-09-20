# -*- coding: utf-8 -*-
from lexicon_miner.models import Lexicon, Word

import numpy as np
import json
import re
import os

class LexClassifier:
    def __init__(self,lexicon,operation='or',match_type='prefix',required_words=1,phrase_slop=0):
        self._match_type = match_type
        # match = prefix | exact | fuzzy
        self._operation = operation
        self._phrase_slop = phrase_slop
        self._required_words = required_words
        self._lexicon = self._parse_lex(lexicon)
        self._patterns = self._generate_patterns(operation)

    def _parse_lex(self,lexicon):
        if isinstance(lexicon,list):
            lex = lexicon
        elif isinstance(lexicon,str):
            lex = self._load_lex(lexicon)
        else:
            lex = []
        return lex

    def _load_lex(self,lexicon):
        words = []
        with open(lexicon) as f:
            content = f.read().strip()
            words = content.split('\n')
        return words

    def _get_prefix(self):
        if self._match_type=='fuzzy':
            prefix = '('
        else:
            prefix = '(\s|^)('
        return prefix

    def _get_suffix(self):
        if self._match_type=='exact':
            suffix = ')(?=(\s|$))'
        else:
            suffix = ')'
        return suffix

    def _get_slop_pattern(self):
        # TODO: so ugly
        slop_pattern = '\s+(\S+\s+){,'+str(self._phrase_slop)+'}'
        return slop_pattern

    def _add_slops(self,lex_words):
        lex_with_slops = []
        if self._phrase_slop == 0:
            lex_with_slops = lex_words
        else:
            slop_pattern = self._get_slop_pattern()
            for phrase in lex_words:
                words = phrase.split()
                pattern = slop_pattern.join(words)
                lex_with_slops.append(pattern)
        return lex_with_slops

    def _generate_patterns(self,operation):
        patterns = []
        prefix = self._get_prefix()
        suffix = self._get_suffix()

        lex_with_slops = self._add_slops(self._lexicon)

        if operation == 'or':
            pattern = '|'.join(lex_with_slops)
            full_pattern = prefix + pattern + suffix
            patterns.append(full_pattern)
        else:
            for w in lex_with_slops:
                full_pattern = prefix + w + suffix
                patterns.append(full_pattern)
        print(patterns)
        return patterns

    def _has_lex_matches(self,text):
        # or-matches
        found_matches = 0
        nr_patterns = len(self._patterns)

        for pattern in self._patterns:
            matches = re.search(pattern,text,flags=re.IGNORECASE)
            if matches:
                if self._operation == 'or':
                    return True
                found_matches+=1
            if (found_matches/float(nr_patterns)) >= self._required_words:
                return True
            if not matches and self._required_words==1:
                return False

        return False

    def _unpack_match(self,match):
        raw_start = match.start()
        raw_end = match.end()
        raw_str_val = match.group()
        if re.search('^\s',raw_str_val):
            raw_start+=1
        if re.search('\s$',raw_str_val):
            raw_end-=1
        spans = [raw_start,raw_end]
        str_val = raw_str_val.strip()
        unpacked_match = {'str_val':str_val,'spans':spans}
        return unpacked_match


    def get_lex_matches(self,doc):
        matches_list = []
        spans = []
        found_matches = 0
        nr_patterns = len(self._patterns)

        for pattern in self._patterns:
            matches = re.finditer(pattern,doc,flags=re.IGNORECASE)
            for i,m in enumerate(matches):
                if i<1:
                    found_matches+=1
                unpacked_match = self._unpack_match(m)
                span = unpacked_match['spans']
                str_val = unpacked_match['str_val']
                matches_list.append({'spans':span,'str_val':str_val.lower()})
                #spans.append(span)

            if found_matches==0 and self._required_words==1:
                break
        if (found_matches/float(nr_patterns)) >= self._required_words:
            return matches_list
        return []


    def classify(self,doc):
        if self._has_lex_matches(doc):
            return True
        return False


class LexTagger(object):
    """Preprocessor implementation for running TEXTA Lexicon Taggers on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map


    def _convert_to_ratio(self,percentage_str):
        percentage_int = int(re.sub('%','',percentage_str).strip())
        ratio = percentage_int/float(100)
        return ratio

    def _all_args_exist(self,**kwargs):
        if not kwargs.get('lexicon_classifier_preprocessor_feature_names', None) or \
           not kwargs.get('lexicon_classifier_preprocessor_lexicons', None) or \
           not kwargs.get('lexicon_classifier_preprocessor_match_types', None) or \
           not kwargs.get('lexicon_classifier_preprocessor_operations', None) or \
           not kwargs.get('lexicon_classifier_preprocessor_slops', None) or \
           not kwargs.get('lexicon_classifier_preprocessor_words_required', None):
            return False
        return True

    def _parse_arguments(self,kwargs):
        input_features = kwargs['input_features']
        lex_ids = [int(_id) for _id in kwargs['lex_ids']]
        match_type = kwargs['match_type']
        operation = kwargs['operation']
        slop = int(kwargs['slop'])
        words_required = self._convert_to_ratio(kwargs['words_required'])

        parsed_args = {'input_features':input_features,'lex_ids':lex_ids,'match_type':match_type,\
                       'operation':operation,'slop':slop,'words_required':words_required}
        return parsed_args


    def _load_arguments(self,**kwargs):
        input_features = json.loads(kwargs['lexicon_classifier_preprocessor_feature_names'])
        lex_ids        = json.loads(kwargs['lexicon_classifier_preprocessor_lexicons'])
        match_type     = json.loads(kwargs['lexicon_classifier_preprocessor_match_types'])[0]
        operation      = json.loads(kwargs['lexicon_classifier_preprocessor_operations'])[0]
        slop           = json.loads(kwargs['lexicon_classifier_preprocessor_slops'])[0]
        words_required = json.loads(kwargs['lexicon_classifier_preprocessor_words_required'])[0]

        loaded_args = {'input_features':input_features,'lex_ids':lex_ids,'match_type':match_type,\
                       'operation':operation,'slop':slop,'words_required':words_required}

        parsed_args = self._parse_arguments(loaded_args)
        return parsed_args

    def _unpack_lexicons(self, lex_ids):
        # {'lex_name_1':[lex_w1,lexw2],'lex_name2':[lex_w2]} etc
        lexicons = {}
        for lex_id in lex_ids:
            words = []
            lex_object = Lexicon.objects.filter(pk=lex_id)[0]
            word_objects = Word.objects.filter(lexicon=lex_id)
            for wo in word_objects:
                words.append(wo.wrd)
            lex_name = lex_object.name
            lexicons[lex_name] = words
        return lexicons

    def _get_classifiers(self,lexicons,args):
        classifiers = {}
        mt = args['match_type']
        op = args['operation']
        slop = args['slop']
        wr = args['words_required']

        for lex_name, lex in lexicons.items():
            classifier = LexClassifier(lex,operation=op,match_type=mt,required_words=wr,phrase_slop=slop)
            classifiers[lex_name] = classifier
        return classifiers

    def _decode_text(self,text):
        try:
            decoded_text = text.decode()
        except AttributeError:
            decoded_text = text
        return decoded_text

    def _get_texts(self,documents,input_feature):
        input_tokens = input_feature.split('.')
        if len(input_tokens) == 1:
            texts = [self._decode_text(document[input_feature]) for document in documents if input_feature in document]
        else:
            t1 = input_tokens[0]
            t2 = input_tokens[1]
            texts = [self._decode_text(document[t1][t2]) for document in documents if input_feature in document]
        return texts

    def transform(self, documents, **kwargs):

        if not self._all_args_exist(**kwargs):
            return documents

        args = self._load_arguments(**kwargs)

        lex_ids = args['lex_ids']
        input_features = args['input_features']

        lexicons_to_apply = self._unpack_lexicons(lex_ids)
        classifiers = self._get_classifiers(lexicons_to_apply,args)

        for input_feature in input_features:
            texts = self._get_texts(documents,input_feature)

            for lex_name, classifier in classifiers.items():
                lex_matches_batch = [classifier.get_lex_matches(text) for text in texts]

                for i, lex_matches in enumerate(lex_matches_batch):
                    texta_facts = []
                    if lex_matches:
                        if 'texta_facts' not in documents[i]:
                            documents[i]['texta_facts'] = []
                        for match in lex_matches:
                            spans = match['spans']
                            str_val = match['str_val']
                            new_fact = {'fact': self._decode_text(lex_name), 'str_val': self._decode_text(str_val), 'doc_path': input_feature, 'spans': json.dumps([spans])}
                            texta_facts.append(new_fact)
                        documents[i]['texta_facts'].extend(texta_facts)


        return {"documents":documents, "meta": {}}
