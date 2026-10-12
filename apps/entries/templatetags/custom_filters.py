import os
import re

from django import template

register = template.Library()


@register.filter
def basename(value):
    """Extracts the basename of a file path"""
    return os.path.basename(value)


@register.filter
def remove_underscores(value: str) -> str:
    return value.replace("_", " ")


@register.filter
def split_highlights(value):
    if value:
        return value.split(";")
    return []


@register.filter
def class_name(obj):
    return obj.__class__.__name__


@register.filter
def kind_label(obj) -> str:
    """A friendly entry-kind name: ``OneLineEntry`` -> "One line"."""
    name = obj if isinstance(obj, str) else obj.__class__.__name__
    name = name.removesuffix("Entry")
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", name).split()
    return " ".join(w.lower() if i else w for i, w in enumerate(words)) or "Entry"
