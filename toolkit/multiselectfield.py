from multiselectfield import MultiSelectField


# https://github.com/goinnn/django-multiselectfield/issues/74
class PatchedMultiSelectField(MultiSelectField):

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)
