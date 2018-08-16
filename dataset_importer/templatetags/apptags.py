import json

from django import template
from json2table import convert

register = template.Library()


@register.filter(name='json2html')
def json2html(value: str)-> str:
	"""
	Converts any JSON formatted string to an HTML table.
	In case a conversion can not be made, because of an incorrect format or empty value,
	an empty string will be returned instead.

	Result of this needs to be inside a "safe" template filter to be rendered properly.

	:param value: Correctly formated JSON string. Or nothing, both are fine.
	:return: HTML table string.
	"""
	build_direction = "LEFT_TO_RIGHT"
	table_attributes = {"class": "table table-striped table-bordered importDetails"}

	try:
		json_obj = json.loads(value)
	except ValueError:
		return ''

	if type(json_obj) is list:
		html = "\n".join([convert(json, build_direction=build_direction, table_attributes=table_attributes) for json in json_obj])
		return html

	elif type(json_obj) is dict:
		html = convert(json_obj, build_direction=build_direction, table_attributes=table_attributes)
		return html
