from uuid import uuid4

from django.core.cache import cache


VICTIM_MAP_CACHE_VERSION_KEY = 'public_victim_map_version'
VICTIM_MAP_HTML_CACHE_TIMEOUT = 86400


def get_victim_map_cache_version():
    return cache.get_or_set(
        VICTIM_MAP_CACHE_VERSION_KEY,
        lambda: uuid4().hex,
        timeout=None,
    )


def invalidate_victim_map_cache():
    cache.set(VICTIM_MAP_CACHE_VERSION_KEY, uuid4().hex, timeout=None)
