from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .homepage import get_homepage_summary, invalidate_homepage_summary
from .models import (
    Analysis_articles,
    Civilian_victims,
    Hero_images,
    Photo_archive,
    Unverified_civilian,
    Video_archive,
    Webinar,
)


def refresh_homepage_summary():
    invalidate_homepage_summary()
    get_homepage_summary(force=True)


def schedule_homepage_refresh():
    transaction.on_commit(refresh_homepage_summary)


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
