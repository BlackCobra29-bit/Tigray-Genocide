import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .forms import Video_Archive_Form
from .homepage import HOMEPAGE_SUMMARY_CACHE_KEY
from .models import Administrator, Tigray_woreda, Video_archive


class AddVideoArchivePerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="video-archive-superuser",
            password="video-archive-password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(user=cls.superuser)
        cls.denied_user = user_model.objects.create_user(
            username="video-archive-denied",
            password="video-archive-password",
        )
        cls.first_woreda = Tigray_woreda.objects.create(
            woreda_name="Video Archive First Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )
        cls.second_woreda = Tigray_woreda.objects.create(
            woreda_name="Video Archive Second Woreda",
            latitude="13.6",
            longitude="39.6",
            zone="Eastern Tigray",
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    def build_payload(self):
        return {
            "location": "Video Archive Test Location",
            "woreda": self.first_woreda.woreda_name,
            "date_of_event": "2021-01-02",
            "description": "Video archive performance test",
            "online_link": "https://www.youtube.com/watch?v=test-video",
        }

    def test_page_loads_only_assets_needed_by_the_form(self):
        response = self.client.get(reverse("add-video-archive"))
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertEqual(html.count("parsley.min.js"), 1)
        self.assertNotIn('enctype="multipart/form-data"', html)
        self.assertLessEqual(len(asset_urls), 20)
        self.assertLess(len(response.content), 40_000)

    def test_woreda_options_are_rendered_from_cached_name_list(self):
        response = self.client.get(reverse("add-video-archive"))
        html = response.content.decode()

        self.assertEqual(
            html.count(f'value="{self.first_woreda.woreda_name}"'),
            1,
        )
        self.assertEqual(
            html.count(f'value="{self.second_woreda.woreda_name}"'),
            1,
        )

    def test_get_reuses_cached_pending_count_and_woreda_names(self):
        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(reverse("add-video-archive"))

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(reverse("add-video-archive"))

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertLessEqual(len(cold_queries), 6)
        self.assertLessEqual(len(warm_queries), 3)

        warm_sql = " ".join(query["sql"] for query in warm_queries).upper()
        self.assertNotIn("COUNT(", warm_sql)
        self.assertNotIn("APP_TIGRAY_WOREDA", warm_sql)

    def test_valid_post_uses_minimal_save_path_and_redirects(self):
        cache.set(HOMEPAGE_SUMMARY_CACHE_KEY, {"cached": True}, 60)

        with patch("App.signals.get_homepage_summary") as rebuild:
            with CaptureQueriesContext(connection) as queries:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        reverse("add-video-archive"),
                        self.build_payload(),
                    )

        self.assertRedirects(
            response,
            reverse("add-video-archive"),
            fetch_redirect_response=False,
        )
        archive = Video_archive.objects.get(
            location="Video Archive Test Location",
        )
        self.assertEqual(archive.author, self.superuser)
        self.assertEqual(archive.woreda, self.first_woreda)
        self.assertEqual(str(archive.date_of_event), "2021-01-02")
        self.assertEqual(
            archive.online_link,
            "https://www.youtube.com/watch?v=test-video",
        )
        self.assertLessEqual(len(queries), 5)

        sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("COUNT(", sql)
        self.assertNotIn("APP_ADMINISTRATOR", sql)
        rebuild.assert_not_called()
        self.assertIsNone(cache.get(HOMEPAGE_SUMMARY_CACHE_KEY))

    def test_invalid_submission_preserves_values_and_displays_errors(self):
        response = self.client.post(
            reverse("add-video-archive"),
            {
                "location": "Preserved Video Location",
                "woreda": self.second_woreda.woreda_name,
                "description": "Preserved video description",
                "online_link": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Preserved Video Location"')
        self.assertContains(response, "Preserved video description")
        self.assertContains(
            response,
            f'value="{self.second_woreda.woreda_name}" selected',
        )
        self.assertIn(
            "online_link",
            response.context["video_archive_form"].errors,
        )
        self.assertFalse(
            Video_archive.objects.filter(
                location="Preserved Video Location",
            ).exists()
        )

    def test_non_superuser_cannot_create_video_archive(self):
        self.client.force_login(self.denied_user)

        response = self.client.post(
            reverse("add-video-archive"),
            self.build_payload(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Video_archive.objects.count(), 0)

    def test_model_form_declares_each_field_once(self):
        self.assertEqual(
            list(Video_Archive_Form().fields),
            [
                "location",
                "woreda",
                "date_of_event",
                "description",
                "online_link",
            ],
        )
