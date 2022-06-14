def check_if_dict_is_subdict(main_dict: dict, potential_subdict: dict, id_field="id", pop_id=True):
    # Pop id from both just in case as they're almost always unique.
    if pop_id:
        main_dict.pop(id_field, None)
        potential_subdict.pop(id_field, None)

    return potential_subdict.items() <= main_dict.items()
