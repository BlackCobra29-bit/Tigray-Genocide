from django.core.cache import cache

from .models import Analysis_articles, Civilian_victims


ADMIN_PENDING_COUNT_CACHE_KEY = "admin:pending-count:v1"
ADMIN_PENDING_COUNT_CACHE_TIMEOUT = 60


def build_admin_pending_count():
    return (
        Civilian_victims.objects.filter(approval=False).count()
        + Analysis_articles.objects.filter(approval=False, draft=False).count()
    )


def get_admin_pending_count():
    return cache.get_or_set(
        ADMIN_PENDING_COUNT_CACHE_KEY,
        build_admin_pending_count,
        ADMIN_PENDING_COUNT_CACHE_TIMEOUT,
    )


def invalidate_admin_pending_count():
    cache.delete(ADMIN_PENDING_COUNT_CACHE_KEY)
