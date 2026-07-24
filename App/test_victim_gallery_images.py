import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from .models import Civilian_victims


TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class VictimGalleryImageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        Path(TEMP_MEDIA_ROOT).mkdir(parents=True, exist_ok=True)

        source = BytesIO()
        Image.new("RGB", (1600, 1200), "#8c2f39").save(
            source,
            format="JPEG",
            quality=95,
        )
        self.victim = Civilian_victims.objects.create(
            full_name="Gallery Victim",
            gender="Female",
            zone="Test Zone",
            perpetrator="Killed by Eritrean forces",
            picture=SimpleUploadedFile(
                "gallery-victim.jpg",
                source.getvalue(),
                content_type="image/jpeg",
            ),
            approval=True,
        )

    def test_gallery_uses_pre_generated_webp_derivative(self):
        output = StringIO()
        call_command(
            "optimize_victim_gallery_images",
            limit=1,
            stdout=output,
        )

        optimized_files = list(
            Path(TEMP_MEDIA_ROOT).glob(
                "civilian_victims_pic/optimized/*.480w.webp"
            )
        )
        self.assertEqual(len(optimized_files), 1)

        with Image.open(optimized_files[0]) as derivative:
            self.assertLessEqual(derivative.width, 480)
            self.assertLessEqual(derivative.height, 480)
            self.assertEqual(derivative.format, "WEBP")

        response = self.client.get(reverse("civilian-victim-photo-page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/optimized/")
        self.assertContains(response, ".480w.webp")
        self.assertContains(response, 'decoding="async"')

    def test_gallery_reuses_the_paginator_count(self):
        cache.delete("public_woreda_list")

        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(
                reverse("civilian-victim-photo-page")
            )

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(cold_response.context["filtered_count"], 1)
        self.assertEqual(len(cold_queries), 3)

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(
                reverse("civilian-victim-photo-page")
            )

        self.assertEqual(warm_response.status_code, 200)
        self.assertEqual(len(warm_queries), 2)
