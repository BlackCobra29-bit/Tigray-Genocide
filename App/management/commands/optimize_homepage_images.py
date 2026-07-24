from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from App.image_optimization import get_optimized_image_url
from App.models import (
    Analysis_articles,
    Civilian_victims,
    Hero_images,
    Photo_archive,
)


class Command(BaseCommand):
    help = "Pre-generate the WebP derivatives used by the homepage."

    def handle(self, *args, **options):
        generated = 0

        def optimize(image_field, width, height, quality=82):
            nonlocal generated
            if not image_field:
                return
            original_url = image_field.url
            optimized_url = get_optimized_image_url(
                image_field,
                max_width=width,
                max_height=height,
                quality=quality,
            )
            if optimized_url and optimized_url != original_url:
                generated += 1

        for hero in Hero_images.objects.only("hero_image").iterator():
            optimize(hero.hero_image, 1920, 1080, quality=84)

        victims = (
            Civilian_victims.objects.filter(approval=True)
            .only("picture")
            .exclude(
                Q(picture="civilian_victims_pic/default.png")
                | Q(picture="civilian_victims_pic/default_female.jpg")
            )[:30]
        )
        for victim in victims:
            optimize(victim.picture, 360, 480)

        articles = (
            Analysis_articles.objects.filter(approval=True, draft=False)
            .select_related("author", "author__administrator")
            .only("thumbnail", "author__administrator__admin_photo")[:9]
        )
        for article in articles:
            optimize(article.thumbnail, 800, 600)
            try:
                optimize(article.author.administrator.admin_photo, 160, 160)
            except (AttributeError, ObjectDoesNotExist):
                continue

        for archive in Photo_archive.objects.only("photo")[:12]:
            optimize(archive.photo, 800, 600)

        self.stdout.write(
            self.style.SUCCESS(
                f"Homepage image optimization complete ({generated} derivatives ready)."
            )
        )
