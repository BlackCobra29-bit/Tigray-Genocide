from django.core.cache import cache

from .models import Tigray_woreda


ADMIN_CIVILIAN_WOREDA_CACHE_KEY = "admin:civilian-woreda-names:v1"
ADMIN_CIVILIAN_WOREDA_CACHE_TIMEOUT = 3600


def get_admin_civilian_woreda_names():
    return cache.get_or_set(
        ADMIN_CIVILIAN_WOREDA_CACHE_KEY,
        lambda: list(
            Tigray_woreda.objects.order_by("woreda_name").values_list(
                "woreda_name",
                flat=True,
            )
        ),
        ADMIN_CIVILIAN_WOREDA_CACHE_TIMEOUT,
    )


def invalidate_admin_civilian_woreda_names():
    cache.delete(ADMIN_CIVILIAN_WOREDA_CACHE_KEY)
