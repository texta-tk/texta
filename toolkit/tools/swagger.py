from drf_yasg.inspectors import SwaggerAutoSchema
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from toolkit.core.health.utils import get_version

schema_view = get_schema_view(
   openapi.Info(
      title = "TEXTA Toolkit REST API",
      default_version = get_version(),
      description = "TEXTA Toolkit REST API",
      contact = openapi.Contact(email="info@texta.ee"),
      license = openapi.License(name="GPLv3"),
   ),
   public = True,
   permission_classes = (permissions.AllowAny,),
)


class CompoundTagsSchema(SwaggerAutoSchema):

    # See https://github.com/axnsan12/drf-yasg/issues/56
    def get_tags(self, operation_keys):
        return [' > '.join(operation_keys[:-1])]