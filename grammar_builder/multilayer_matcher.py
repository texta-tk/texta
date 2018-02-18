#Intersect
#Union
#Concatenate
#Gap
#Match
#Regex

import re
import itertools

delimiter = r'\s+'

class Match(object):
    def __init__(self, token_idxs, features, texts=None):
        self.token_idxs = tuple(token_idxs) #frozenset(token_idxs if isinstance(token_idxs,list) else [token_idxs])
        self.features = tuple(features)
        self.texts = tuple(texts) #tuple(texts if isinstance(texts,list) else [texts])

    def __repr__(self):
        return "Match(token_idxs=%s, features=%s, texts=%s)"%(self.token_idxs, self.features, self.texts)
    
    def __eq__(self, other):
        return self.token_idxs == other.token_idxs and self.features == other.features
        
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        return hash((self.token_idxs,self.features))

#{'Comment':'asd', 'Comment.lemmas':'asdike'}
class LayerDict(dict):
    def __init__(self, layers_dict):
        super(LayerDict,self).__init__()
        for layer_path in layers_dict:
            split_layer_path = layer_path.split('.')
            feature_name, layer_name = split_layer_path if len(split_layer_path) == 2 else (split_layer_path[0], None)
            if feature_name not in self:
                self[feature_name] = {}
            if layer_name not in self[feature_name]:
                self[feature_name][layer_name] = {}
            self[feature_name][layer_name]['text'] = layers_dict[layer_path]
            self[feature_name][layer_name]['map'] = None
            self[feature_name][layer_name]['starts'] = None

    def get_token_index(self, feature_name, layer_name, match_location):
        if not self[feature_name][layer_name]['map']:
            self[feature_name][layer_name]['map'] = self._get_char_to_token_mapping(feature_name, layer_name)
        return self[feature_name][layer_name]['map'][match_location]

    def get_token_by_index(self, token_idx, feature_name, layer_name):
        if feature_name not in self or layer_name not in self[feature_name]:
            return None
        mapping = self[feature_name][layer_name]['map']
        if not self[feature_name][layer_name]['starts']:
            self[feature_name][layer_name]['starts'] = self._get_index_to_char_start_mapping(feature_name, layer_name)
        
        start_idx = self[feature_name][layer_name]['starts'][token_idx]
        end_idx = start_idx + 1
        while end_idx < len(mapping):
            if mapping[end_idx] != token_idx:
                break
            end_idx += 1
        end_idx = end_idx + 1 if end_idx == (len(mapping) - 1) else end_idx

        return self[feature_name][layer_name]['text'][start_idx:end_idx]
    
    def _get_char_to_token_mapping(self, feature_name, layer_name):
        pattern = re.compile('([^'+delimiter+']+)')
        encoded_layer = [None]*len(self[feature_name][layer_name]['text'])
        spans = [(match.start(),match.end()) for match in pattern.finditer(self[feature_name][layer_name]['text'])]
        for span_idx, span in enumerate(spans):
            for position in range(span[0],span[1]):
                encoded_layer[position] = span_idx
        return encoded_layer

    def _get_index_to_char_start_mapping(self, feature_name, layer_name):
        index_to_char_start = []
        last_token_idx = -1
        mapping = self[feature_name][layer_name]['map']
        for idx in range(len(self[feature_name][layer_name]['map'])):
            token_idx = mapping[idx]
            if token_idx != last_token_idx:
                index_to_char_start.append(idx)
            last_token_idx = token_idx
            
        return index_to_char_start

class Exact(object):
    def __init__(self, tokens, layer_path, case_sensitive=False):
        split_layer_path = layer_path.split('.')
        self._feature_name, self._layer_name = split_layer_path if len(split_layer_path) == 2 else (split_layer_path[0],None)
        if case_sensitive:
            self._pattern = re.compile('|'.join([re.escape(token) for token in tokens]))
        else:
            self._pattern = re.compile('|'.join([re.escape(token) for token in tokens]),re.IGNORECASE)
        
    def match(self, layer_dict):
        results = []

        if layer_dict:        
            for match in re.finditer(self._pattern,layer_dict[self._feature_name][self._layer_name]['text']):
                start_location, end_location = match.start(), match.end()
                token_idxs = [token_idx for token_idx in 
                              range(layer_dict.get_token_index(self._feature_name, self._layer_name, start_location),
                                    layer_dict.get_token_index(self._feature_name, self._layer_name, end_location-1)+1)] 
                results.append(Match(token_idxs,[self._feature_name]*len(token_idxs),[layer_dict.get_token_by_index(token_idx,self._feature_name,self._layer_name) for token_idx in token_idxs]))
        return results
    
class Regex(object):
    def __init__(self, regex_string, layer_path, case_sensitive=False):
        split_layer_path = layer_path.split('.')
        self._feature_name, self._layer_name = split_layer_path if len(split_layer_path) == 2 else (split_layer_path[0],None)
        if case_sensitive:
            self._pattern = re.compile(regex_string)
        else:
            self._pattern = re.compile(regex_string,re.IGNORECASE)
        
    def match(self, layer_dict):
        results = []
        for match in re.finditer(self._pattern,layer_dict[self._feature_name][self._layer_name]['text']):
            start_location, end_location = match.start(), match.end()
            token_idxs = [token_idx for token_idx in 
                          range(layer_dict.get_token_index(self._feature_name, self._layer_name, start_location),
                                layer_dict.get_token_index(self._feature_name, self._layer_name, end_location-1)+1)] 
            results.append(Match(token_idxs,[self._feature_name]*len(token_idxs),[layer_dict.get_token_by_index(token_idx, self._feature_name, self._layer_name)
                                                                  for token_idx in token_idxs]))
        return results
        
class Intersection(object):
    def __init__(self, components, match_first=False):
        self._components = components
        self._match_first = match_first
        
    def match(self, layer_dict):
        component_matches = [component.match(layer_dict) for component in self._components]
        
        # Using Cartesian product to get all the possible match combinations
        match_combinations = [match for match in itertools.product(*component_matches)]
        
        if self._match_first:
            match_combinations = self._filter_out_distant_matches(match_combinations)
        
        matches = []
        
        for match_combination in match_combinations: 
            matches.append(self._merge_matches(match_combination))
        return list(set(matches))

    def _merge_matches(self, matches):
        token_idxs = []
        features = []
        texts = []
        
        for match in matches:
            token_idxs.extend(match.token_idxs)
            features.extend(match.features)
            texts.extend(match.texts)

        return Match(token_idxs, features, texts)

    def _filter_out_distant_matches(self, match_components):
        filtered_components = []
        
        aggregated_components = [[token_idx for match in matches for token_idx in match.token_idxs] for matches in match_components]
        
        aggregated_component_summed_diffs = [sum(abs(next_token_idx - prev_token_idx) if len(aggregated_components[component_idx]) >= 2 else 0
                                             for prev_token_idx, next_token_idx in
                                             zip(aggregated_components[component_idx], aggregated_components[component_idx][1:]))
                                             for component_idx in range(aggregated_components)]
        
        sorted_components = [match_components[component_idx] for component_idx in argsort(aggregated_component_summed_diffs)]
        
        visited_tokens = set()
        
        for component in sorted_components:
            if not visited_tokens & set(match.token_idxs for match in component):
                filtered_matches.append(component)
                
        return filtered_components

class Union(object):
    def __init__(self, components):
        self._components = components
        
    def match(self, layer_dict):        
        return list(set([component_match for component in self._components for component_match in component.match(layer_dict)]))

class Concatenation(object):
    def __init__(self, components):
        self._components = components
        
    def match(self, layer_dict):
        intersection_results = Intersection(self._components).match(layer_dict)
        return [match for match in intersection_results if self._is_match_a_concatenation(match, layer_dict)]
        
    def _is_match_a_concatenation(self, match, layer_dict):
        if len(match.token_idxs) < 2:
            return True

        #sorted_token_idxs = sorted(match.token_idxs)
        #return all(prev_token_idx + 1 ==  next_token_idx for prev_token_idx, next_token_idx in zip(sorted_token_idxs,sorted_token_idxs[1:]))
        return all(prev_token_idx + 1 ==  next_token_idx for prev_token_idx, next_token_idx in zip(match.token_idxs,match.token_idxs[1:]))
    
class Gap(object):
    def __init__(self, components, slop=None, match_first=False):
        self._components = components
        self._slop = int(slop) if slop else float('inf')
        self._match_first = match_first
        
    def match(self, layer_dict):
        intersection_results = Intersection(self._components, match_first=self._match_first).match(layer_dict)
        return [match for match in intersection_results if self._is_match_within_gap(match, layer_dict)]
    
    def _is_match_within_gap(self, match, layer_dict):
        if len(match.token_idxs) < 2:
            return True
        
        #sorted_token_idxs = sorted(match.token_idxs)
        #all_ = all(0 < next_token_idx - prev_token_idx <= self._slop for prev_token_idx, next_token_idx in zip(sorted_token_idxs,sorted_token_idxs[1:]))
        return all(0 < next_token_idx - prev_token_idx <= self._slop for prev_token_idx, next_token_idx in zip(match.token_idxs,match.token_idxs[1:]))

class LayerMatch(object):
    def __init__(self, components):
        self._components = components
        
    def match(self, layer_dict):
        component_matches = [component.match(layer_dict) for component in self._components]
        
        matches = []
        for match_combination in itertools.product(*component_matches): # Using Cartesian product to get all the possible match combinations
            if self._have_matching_token_indices(match_combination):
                matches.append(self._merge_matches(match_combination))
            
        return matches
        
    def _have_matching_token_indices(self, matches):
        if len(matches) < 2:
            return True
        
        max_tokens = max(matches, key= lambda match: len(match.token_idxs))
        if not all(len(match.token_idxs) in set([1,max_tokens]) for match in matches): # Incompatible match lengths
            return False
        
        tokens_indices = []
        for match in matches:   # Expand matches with one token
            if len(match.token_idxs) == 1:
                tokens_indices.append(match.token_idxs*max_tokens)
            else:
                tokens_indices.append(match.token_idxs)

        return all(prev_token_indxs == next_token_indxs for prev_token_indxs, next_token_indxs in zip(tokens_indices, tokens_indices[1:]))
        
    def _merge_matches(self, matches):
        token_idxs = []
        features = []
        texts = []
        
        for match in matches:
            token_idxs.extend(match.token_idxs)
            features.extend(match.features)
            texts.extend(match.texts)

        return Match(token_idxs, features, texts)

def filter_matches_for_highlight(matches):
    pass

def get_all_combinations(values):
    combinations = []
    
    def gather_combinations(values,current_combination,idx):
        if idx == len(values):
            combinations.append(current_combination)
            return
        gather_combinations(values,current_combination+[values[idx]],idx+1)
        gather_combinations(values,current_combination+[],idx+1)    

    gather_combinations(values,[],0)
    return combinations
 
def argsort(iterable):
    return sorted(range(len(iterable)), key=iterable.__getitem__)
 
#     0    1     2   3     4    5    6  7   8     9        
s = "tere ohsa tere pere vaike kere mis sa ikka pere"

from pprint import pprint

ld = LayerDict({'text':s})

"""
ex = Exact(["tere","kere"],"text",None)
reg = Regex(".ere","text")

pprint(Exact(["tere","kere"],"text",None).match(ld))
pprint(Regex(".ere","text").match(ld))

pprint(Intersection([ex,reg]).match(ld))
"""

"""
ex1 = Exact(["tere"],"text")
ex2 = Exact(["pere"],"text")

#pprint(ex1.match(ld))
#pprint(ex2.match(ld))
pprint(Intersection([ex1,ex2]).match(ld))

pprint(Union([ex1,ex2,ex2]).match(ld))


pprint(Concatenation([ex1,ex2]).match(ld))
print
pprint(Gap([ex1,ex1],1).match(ld))
"""

"""
text = "liisa vaatas hobust ja naeratas hobulikult ja"
lemmas = "liisa vaatama hobune ja naeratama hobune ja"
pos = "N V N S V A S"

ld = LayerDict({'text':text,'lemmas':lemmas,'pos':pos})

ex_hobune = Exact(["hobune"],'lemmas')
ex_ja = Exact(["ja"],'lemmas')
ex_a = Exact(["A"],'pos')
int_hobune_ja = Intersection([ex_hobune,ex_a])
pprint(int_hobune_ja.match(ld))
"""
