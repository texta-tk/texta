def add_dicts(dict1, dict2):
    '''
    Helper function to += values of keys from two dicts with a single level nesting
    '''
    # Check if params are dict
    # Dicts are passed in as reference, so dict1 gets updated from call
    if set([type(dict1), type(dict2)]).issubset([dict]):
        for key, val in dict2.items():
            if key not in dict1:
                dict1[key] = val
            else:
                if type(val) == dict:
                    for k, v in val.items():
                        if type(v) != dict:
                            dict1[key][k] += v
                else:
                    dict1[key] += val
