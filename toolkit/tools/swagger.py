from drf_yasg.inspectors import SwaggerAutoSchema

class CompoundTagsSchema(SwaggerAutoSchema):

    # See https://github.com/axnsan12/drf-yasg/issues/56
    def get_tags(self, operation_keys):
        return [' > '.join(operation_keys[:-1])]