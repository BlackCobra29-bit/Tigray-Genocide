from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django_summernote.utils import get_attachment_model

from .admin_civilian_form import invalidate_admin_civilian_woreda_names
from .admin_metrics import invalidate_admin_pending_count
from .dashboard_summary import invalidate_admin_dashboard_summary
from .homepage import get_homepage_summary, invalidate_homepage_summary
from .image_cleanup import (
    remember_deleted_images,
    remember_replaced_images,
    schedule_deleted_image_cleanup,
    schedule_replaced_image_cleanup,
)
from .image_uploads import replace_field_file_with_webp
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


SummernoteAttachment = get_attachment_model()


@receiver(
    pre_save,
    sender=SummernoteAttachment,
    dispatch_uid="convert_summernote_image_upload_to_webp",
)
def convert_summernote_image_upload_to_webp(sender, instance, **kwargs):
    """Normalize images inserted inside article and webinar editors too."""
    if kwargs.get("raw", False):
        return

    attachment = instance.file
    if attachment and not attachment._committed:
        original_name = attachment.name
        replace_field_file_with_webp(attachment)
        if not instance.name or instance.name == original_name:
            instance.name = attachment.name


@receiver(pre_save, dispatch_uid="remember_replaced_webp_images")
def remember_replaced_webp_images(sender, instance, **kwargs):
    if not kwargs.get("raw", False):
        remember_replaced_images(
            sender,
            instance,
            update_fields=kwargs.get("update_fields"),
        )


@receiver(post_save, dispatch_uid="cleanup_replaced_webp_images")
def cleanup_replaced_webp_images(sender, instance, **kwargs):
    if not kwargs.get("raw", False):
        schedule_replaced_image_cleanup(sender, instance)


@receiver(pre_delete, dispatch_uid="remember_deleted_webp_images")
def remember_deleted_webp_images(sender, instance, **kwargs):
    remember_deleted_images(sender, instance)


@receiver(post_delete, dispatch_uid="cleanup_deleted_webp_images")
def cleanup_deleted_webp_images(sender, instance, **kwargs):
    schedule_deleted_image_cleanup(sender, instance)


def refresh_homepage_summary():
    invalidate_homepage_summary()
    get_homepage_summary(force=True)


def schedule_homepage_refresh():
    transaction.on_commit(refresh_homepage_summary)


def schedule_homepage_invalidation():
    transaction.on_commit(invalidate_homepage_summary)


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


@receiver(post_save, sender=Hero_images)
@receiver(post_delete, sender=Hero_images)
def refresh_homepage_on_change(sender, **kwargs):
    schedule_homepage_refresh()


@receiver(post_save, sender=Video_archive)
@receiver(post_delete, sender=Video_archive)
def invalidate_homepage_after_video_archive_change(sender, **kwargs):
    # Video archive changes should not wait for the homepage summary rebuild.
    # The next homepage request will repopulate the invalidated cache.
    schedule_homepage_invalidation()


@receiver(post_save, sender=Photo_archive)
@receiver(post_delete, sender=Photo_archive)
def invalidate_homepage_after_photo_archive_change(sender, **kwargs):
    # Photo archive changes should not wait for the homepage summary rebuild.
    # The next homepage request will repopulate the invalidated cache.
    schedule_homepage_invalidation()


@receiver(post_save, sender=Civilian_victims)
@receiver(post_delete, sender=Civilian_victims)
@receiver(post_save, sender=Unverified_civilian)
@receiver(post_delete, sender=Unverified_civilian)
def invalidate_homepage_after_civilian_change(sender, **kwargs):
    # Civilian changes should not wait for homepage charts to be rebuilt.
    # The next homepage request repopulates the invalidated summary cache.
    schedule_homepage_invalidation()


@receiver(post_save, sender=Analysis_articles)
@receiver(post_delete, sender=Analysis_articles)
def invalidate_homepage_after_article_change(sender, **kwargs):
    # Article writing should not wait for the homepage summary to be rebuilt.
    # The next homepage request will repopulate the invalidated cache.
    schedule_homepage_invalidation()


@receiver(post_save, sender=Webinar)
@receiver(post_delete, sender=Webinar)
def invalidate_homepage_after_webinar_change(sender, **kwargs):
    # Panel discussion changes should not wait for the homepage summary rebuild.
    # The next homepage request will repopulate the invalidated cache.
    schedule_homepage_invalidation()


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
