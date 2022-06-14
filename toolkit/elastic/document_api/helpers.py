def check_if_dict_is_subdict(main_dict: dict, potential_subdict: dict):
    is_subset = potential_subdict.items() <= main_dict.items()
    return is_subset
