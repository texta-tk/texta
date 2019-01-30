from django import template
import json

register = template.Library()

@register.simple_tag
def get_field(value):
    return json.dumps(json.loads(value)['fields'])