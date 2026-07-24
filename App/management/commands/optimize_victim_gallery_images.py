from django.core.management.base import BaseCommand

from App.image_optimization import get_optimized_image_url
from App.models import Civilian_victims


class Command(BaseCommand):
    help = "Pre-generate the WebP derivatives used by the victim photo gallery."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            help="Process at most this many unique victim images.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        seen_names = set()
        derivatives_ready = 0

        victims = (
            Civilian_victims.objects.filter(approval=True)
            .exclude(picture="")
            .only("picture")
            .iterator(chunk_size=500)
        )

        for victim in victims:
            source_name = victim.picture.name
            if not source_name or source_name in seen_names:
                continue

            seen_names.add(source_name)
            original_url = victim.picture.url
            optimized_url = get_optimized_image_url(
                victim.picture,
                max_width=480,
                max_height=480,
                quality=80,
            )

            if optimized_url and optimized_url != original_url:
                derivatives_ready += 1

            if limit is not None and len(seen_names) >= limit:
                break

        self.stdout.write(
            self.style.SUCCESS(
                "Victim gallery image optimization complete "
                f"({derivatives_ready} of {len(seen_names)} unique derivatives ready)."
            )
        )
