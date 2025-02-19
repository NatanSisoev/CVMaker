# cv/templatetags/cv_filters.py
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