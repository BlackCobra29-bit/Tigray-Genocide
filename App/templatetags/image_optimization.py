from django import template

from App.image_optimization import get_optimized_image_url


register = template.Library()


@register.simple_tag
def optimized_image_url(image_field, max_width, max_height=None, quality=82):
    return get_optimized_image_url(
        image_field,
        max_width=max_width,
        max_height=max_height,
        quality=quality,
    )
