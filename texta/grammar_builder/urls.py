from django.conf.urls import url

from ..grammar_builder.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'get_table_data', get_table_data, name='get_table_data'),
    url(r'get_table', get_table, name='get_table'),
    url(r'save_component', save_component, name='save_component'),
    url(r'get_components', get_components, name='get_components'),
    url(r'get_component_json', get_component_JSON, name='get_component_json'),
    url(r'get_grammar_listing', get_grammar_listing, name='get_grammar_listing'),
    url(r'get_grammar', get_grammar, name='get_grammar'),
    url(r'save_grammar', save_grammar, name='save_grammar'),
    url(r'delete_grammar', delete_grammar, name='delete_grammar'),
]
