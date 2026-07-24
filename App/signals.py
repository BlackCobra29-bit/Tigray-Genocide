from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .admin_civilian_form import invalidate_admin_civilian_woreda_names
from .admin_metrics import invalidate_admin_pending_count
from .dashboard_summary import invalidate_admin_dashboard_summary
from .homepage import get_homepage_summary, invalidate_homepage_summary
from .models import (
    Analysis_articles,
    Civilian_victims,
    Hero_images,
    Photo_archive,
    Tigray_woreda,
    Unverified_civilian,
    Video_archive,
    Webinar,
)
from .victim_map_cache import invalidate_victim_map_cache


def refresh_homepage_summary():
    invalidate_homepage_summary()
    get_homepage_summary(force=True)


def schedule_homepage_refresh():
    transaction.on_commit(refresh_homepage_summary)


def schedule_admin_dashboard_invalidation():
    transaction.on_commit(invalidate_admin_dashboard_summary)


def schedule_admin_pending_count_invalidation():
    transaction.on_commit(invalidate_admin_pending_count)


def schedule_victim_map_invalidation():
    transaction.on_commit(invalidate_victim_map_cache)


def refresh_woreda_map_data():
    cache.delete('public_woreda_list')
    invalidate_admin_civilian_woreda_names()
    invalidate_victim_map_cache()


def schedule_woreda_map_refresh():
    transaction.on_commit(refresh_woreda_map_data)


@receiver(post_save, sender=Civilian_victims)
@receiver(post_delete, sender=Civilian_victims)
@receiver(post_save, sender=Unverified_civilian)
@receiver(post_delete, sender=Unverified_civilian)
@receiver(post_save, sender=Analysis_articles)
@receiver(post_delete, sender=Analysis_articles)
@receiver(post_save, sender=Photo_archive)
@receiver(post_delete, sender=Photo_archive)
@receiver(post_save, sender=Video_archive)
@receiver(post_delete, sender=Video_archive)
@receiver(post_save, sender=Webinar)
@receiver(post_delete, sender=Webinar)
@receiver(post_save, sender=Hero_images)
@receiver(post_delete, sender=Hero_images)
def refresh_homepage_on_change(sender, **kwargs):
    schedule_homepage_refresh()


@receiver(post_save, sender=Civilian_victims)
@receiver(post_delete, sender=Civilian_victims)
@receiver(post_save, sender=Unverified_civilian)
@receiver(post_delete, sender=Unverified_civilian)
@receiver(post_save, sender=Analysis_articles)
@receiver(post_delete, sender=Analysis_articles)
@receiver(post_save, sender=Photo_archive)
@receiver(post_delete, sender=Photo_archive)
@receiver(post_save, sender=Video_archive)
@receiver(post_delete, sender=Video_archive)
@receiver(post_save, sender=Webinar)
@receiver(post_delete, sender=Webinar)
def invalidate_admin_dashboard_on_change(sender, **kwargs):
    schedule_admin_dashboard_invalidation()


@receiver(post_save, sender=Civilian_victims)
@receiver(post_delete, sender=Civilian_victims)
@receiver(post_save, sender=Analysis_articles)
@receiver(post_delete, sender=Analysis_articles)
def invalidate_admin_pending_count_on_change(sender, **kwargs):
    schedule_admin_pending_count_invalidation()


@receiver(post_save, sender=Civilian_victims)
@receiver(post_delete, sender=Civilian_victims)
def invalidate_victim_map_on_change(sender, **kwargs):
    schedule_victim_map_invalidation()


@receiver(post_save, sender=Tigray_woreda)
@receiver(post_delete, sender=Tigray_woreda)
def invalidate_woreda_map_on_change(sender, **kwargs):
    schedule_woreda_map_refresh()
