from django import template

register = template.Library()

@register.filter(name='input_class')
def input_class(field):
    """
    Returns the appropriate CSS class for a form field
    """
    if field.errors:
        return "form-control is-invalid"
    return "form-control"

@register.filter
def class_name(value):
    return value.__class__.__name__

@register.filter
def split_highlights(value):
    if value:
        return value.split(";")
    return []

@register.filter
def get_form(dictionary, key):
    return dictionary.get(key).as_p()