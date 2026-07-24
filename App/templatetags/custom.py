
from functools import lru_cache

from django import template
from urlextract import URLExtract

register = template.Library()

_url_extractor = URLExtract()


@lru_cache(maxsize=4096)
def _extract_urls(value):
    return tuple(_url_extractor.find_urls(value))

@register.filter
def extract_and_join_urls(value):
    """
    Custom Django template filter to extract URLs from a string and join them into a single string.
    """
    if not value:
        return ''
    return ', '.join(_extract_urls(str(value)))

@register.filter(name='split_string')
def split_string(value, delimiter):
    return value.split(delimiter)
    
@register.filter(name='zip_lists')
def zip_lists(list1, list2):
    return zip(list1, list2)


@register.simple_tag
def page_numbers(paginator, current_page, on_each_side=1, on_ends=1):
    return list(
        paginator.get_elided_page_range(
            number=current_page,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    )
