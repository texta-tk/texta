# -*- coding: utf-8 -*-
from lexicon_miner.models import Lexicon, Word
from texta.settings import ERROR_LOGGER
import numpy as np
import logging
import json
import re
import os

class LexClassifier:
    def __init__(self,lexicon,operation='or',match_type='prefix',required_words=1,phrase_slop=0,counter_slop=0,counter_lexicon=[]):
        """
        :param lexicon: lexicon containing words/phrases/regexes to match
        :param operation: logic operation used between the lexicon entries ('or','and')
        :param match_type: how to match lexicon entries ('prefix','fuzzy','exact')
        :param required_words: the proportion of words required to be in the text to obtain the tag (only for operation='and')
        :param phrase_slop: how many words are allowed between lexicon phrase entities
        :param counter_slop: how many words are allowed between nullifying lex entries and main lex entries
        :param counter_lexicon: lexicon containing words/phrases/regexes which nullify main lex words
        :type lexicon: list or string (containing lex file name)
        :type operation: string
        :type match_type: string
        :type required_words: float (in range [0,1])
        :type phrase_slop: int
        :type counter_slop: int
        :type counter_lexicon: list or string (containing lex file name)
        """
        self._match_type = match_type
        self._operation = operation
        self._phrase_slop = phrase_slop
        self._required_words = required_words
        self._counter_lexicon = self._parse_lex(counter_lexicon)
        self._lexicon = self._parse_lex(lexicon)
        self._patterns = self._generate_patterns(self._lexicon, operation,match_type)
        self._counter_patterns = self._generate_patterns(self._counter_lexicon, operation='or',match_type='exact')
        self._counter_slop = counter_slop

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

    def _get_prefix(self,match_type):
        if match_type=='fuzzy':
            prefix = '(\w*'
        else:
            prefix = '(\s|^)('
        return prefix

    def _get_suffix(self,match_type):
        if match_type=='exact':
            suffix = ')(?=((\W*)\s|$))'
        else:
            suffix = '\w*)(?=\W*)'
        return suffix

    def _get_slop_pattern(self):
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

    def _dispend_counter_matches(self,counter_matches,unpacked_match,doc):
        match = unpacked_match[0]
        match_start = match['spans'][0]

        for counter_match in counter_matches:
            counter_match_end = counter_match['spans'][1]

            if counter_match_end < match_start:
                section = doc[counter_match_end+1:match_start]
                words = section.split()
                if len(words) <= self._counter_slop:
                    return []
        return unpacked_match


    def _generate_patterns(self,lexicon,operation,match_type):
            patterns = []
            prefix = self._get_prefix(match_type)
            suffix = self._get_suffix(match_type)

            lex_with_slops = self._add_slops(lexicon)

            if operation == 'or':
                pattern = '|'.join(lex_with_slops)
                full_pattern = prefix + pattern + suffix
                patterns.append(full_pattern)
            else:
                for w in lex_with_slops:
                    full_pattern = prefix + w + suffix
                    patterns.append(full_pattern)
            return patterns

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
        unpacked_match = [{'str_val':str_val.lower(),'spans':spans}]
        return unpacked_match

    def _get_counter_matches(self,doc):
        counter_matches = []
        for pattern in self._counter_patterns:
            matches = re.finditer(pattern,doc,flags=re.IGNORECASE)
            for match in matches:
                unpacked_match = self._unpack_match(match)
                counter_matches.extend(unpacked_match)
        return counter_matches

    def get_lex_matches(self,doc):
        matches_list = []
        found_matches = 0
        nr_patterns = len(self._patterns)

        counter_matches = self._get_counter_matches(doc)

        for pattern in self._patterns:
            matches = re.finditer(pattern,doc,flags=re.IGNORECASE)
            for i,m in enumerate(matches):

                unpacked_match = self._unpack_match(m)

                if self._counter_lexicon:
                    unpacked_match = self._dispend_counter_matches(counter_matches,unpacked_match,doc)

                if i<1 and unpacked_match:
                    found_matches+=1

                matches_list.extend(unpacked_match)

            if found_matches==0 and self._required_words==1:
                break

        if (found_matches/float(nr_patterns)) >= self._required_words:
            return matches_list
        return []

class LexTagger(object):
    """Preprocessor implementation for running TEXTA Lexicon Taggers on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map


    def _convert_to_ratio(self,percentage_str):
        percentage_int = int(percentage_str.strip())
        ratio = percentage_int/float(100)
        return ratio

    def _all_args_exist(self,**kwargs):
        if not kwargs.get('lexicon_classifier_preprocessor_feature_names', None):
            return False
        return True

    def _load_input_features(self,**kwargs):
        try:
            input_features = [json.loads(inp_feature)['path'] for inp_feature in json.loads(kwargs['lexicon_classifier_preprocessor_feature_names']) if json.loads(inp_feature)['type']=='text']
        except:
            try:
                input_features = json.loads(kwargs['lexicon_classifier_preprocessor_feature_names'])
            except:
                logging.getLogger(ERROR_LOGGER).info('Did not detect any input features.', exc_info=True)
                input_features = []
        return input_features


    def _parse_arguments(self,kwargs):
        input_features = kwargs['input_features']
        lex_ids = [int(_id) for _id in kwargs['lex_ids']]
        cl_id   = [int(kwargs['counter_lex_id'])]
        match_type = kwargs['match_type'].lower()
        operation = kwargs['operation'].lower()
        slop = int(kwargs['slop'])
        cl_slop = int(kwargs['cl_slop'])
        words_required = self._convert_to_ratio(kwargs['words_required'])

        parsed_args = {'input_features':input_features,'lex_ids':lex_ids,'match_type':match_type,\
                       'operation':operation,'slop':slop,'words_required':words_required,'cl_slop':cl_slop,\
                       'counter_lex_id':cl_id}
        return parsed_args

    def _load_arguments(self,kwargs):
        input_features  = self._load_input_features(**kwargs)
        lex_ids         = json.loads(kwargs['lexicon_classifier_preprocessor_lexicons'])
        match_type      = json.loads(kwargs['lexicon_classifier_preprocessor_match_types'])[0]
        operation       = json.loads(kwargs['lexicon_classifier_preprocessor_operations'])[0]
        slop            = json.loads(kwargs['lexicon_classifier_preprocessor_slops'])[0]
        words_required  = json.loads(kwargs['lexicon_classifier_preprocessor_words_required'])[0]
        counter_lex_id  = json.loads(kwargs['lexicon_classifier_preprocessor_counterlexicons'])[0]
        cl_slop         = json.loads(kwargs['lexicon_classifier_preprocessor_cl_slops'])[0]

        add_counter_lex = False

        if 'lexicon_classifier_preprocessor_add_cl' in kwargs:
            add_counter_lex = True

        args_to_parse = {'input_features':input_features,'lex_ids':lex_ids,'match_type':match_type,\
                         'operation':operation,'slop':slop,'words_required':words_required,'cl_slop':cl_slop,\
                         'counter_lex_id':counter_lex_id}

        loaded_args = {'add_counter_lex':add_counter_lex}
        parsed_args = self._parse_arguments(args_to_parse)
        loaded_args.update(parsed_args)

        return loaded_args

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

    def _get_classifiers(self,lexicons,counter_lexicon,args):
        classifiers = {}
        mt = args['match_type']
        op = args['operation']
        slop = args['slop']
        wr = args['words_required']
        cs = args['cl_slop']
        add_cl = args['add_counter_lex']

        for lex_name, lex in lexicons.items():
            if add_cl:
                classifier = LexClassifier(lex,operation=op,match_type=mt,required_words=wr,phrase_slop=slop,counter_slop=cs,counter_lexicon=counter_lexicon)
            else:
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

        args = self._load_arguments(kwargs)

        lex_ids = args['lex_ids']
        counter_lex_ids = args['counter_lex_id']
        input_features = args['input_features']

        lexicons_to_apply = self._unpack_lexicons(lex_ids)

        counter_lexicon = list(self._unpack_lexicons(counter_lex_ids).items())[0][1]
        classifiers = self._get_classifiers(lexicons_to_apply,counter_lexicon,args)

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
