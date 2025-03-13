import os

from django import template

register = template.Library()

@register.filter
def basename(value):
    """Extracts the basename of a file path"""
    return os.path.basename(value)

@register.filter
def remove_underscores(value: str) -> str:
    return value.replace('_', ' ')

@register.filter
def split_highlights(value):
    if value:
        return value.split(";")
    return []

@register.filter
def class_name(obj):
    return obj.__class__.__name__
