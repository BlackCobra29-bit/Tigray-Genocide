import io
import re
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .homepage import HOMEPAGE_SUMMARY_CACHE_KEY
from .models import Administrator, Analysis_articles


class WriteArticlePerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_user(
            username="article-superuser",
            password="article-password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(
            user=cls.superuser,
            analysis_role=True,
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def build_payload(self, title="Performance Test Article"):
        image_data = io.BytesIO()
        Image.new("RGB", (2, 2), color="green").save(
            image_data,
            format="PNG",
        )
        return {
            "title": title,
            "thumbnail": SimpleUploadedFile(
                "article.png",
                image_data.getvalue(),
                content_type="image/png",
            ),
            "content": "<p>Article body</p>",
            "endf_related": "on",
        }

    def test_page_loads_summernote_and_parsley_without_unused_libraries(self):
        response = self.client.get(reverse("write-article"))
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_content_iframe"')
        self.assertNotIn("/static/admin/js/vendor/jquery/jquery.js", html)
        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertEqual(html.count("parsley.min.js"), 1)
        self.assertIn("sweetalert2@10", html)
        self.assertNotIn(
            '<script src="https://cdn.jsdelivr.net/npm/sweetalert2@10"',
            html,
        )
        self.assertContains(response, "article-saving-spinner")
        self.assertLessEqual(len(asset_urls), 20)
        self.assertLess(len(response.content), 40_000)

    def test_page_reuses_cached_pending_count_and_administrator(self):
        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(reverse("write-article"))

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(reverse("write-article"))

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertLessEqual(len(cold_queries), 5)
        self.assertLessEqual(len(warm_queries), 3)
        administrator_queries = [
            query for query in warm_queries
            if "App_administrator" in query["sql"]
        ]
        self.assertEqual(len(administrator_queries), 1)

    def test_ajax_publish_saves_with_bounded_queries(self):
        with CaptureQueriesContext(connection) as queries:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("write-article"),
                    self.build_payload(),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        article = Analysis_articles.objects.get(
            title="Performance Test Article",
        )
        self.assertEqual(article.author, self.superuser)
        self.assertTrue(article.approval)
        self.assertFalse(article.draft)
        self.assertTrue(article.endf_related)
        self.assertLessEqual(len(queries), 5)

        sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("COUNT(", sql)
        self.assertNotIn("APP_ADMINISTRATOR", sql)

    def test_ajax_draft_uses_the_same_fast_save_path(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("draft-article"),
                self.build_payload(title="Draft Performance Article"),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        article = Analysis_articles.objects.get(
            title="Draft Performance Article",
        )
        self.assertTrue(article.draft)
        self.assertEqual(
            response.json()["message"],
            "New analysis article saved to draft...",
        )

    def test_ajax_validation_error_returns_json_and_preserves_database(self):
        response = self.client.post(
            reverse("write-article"),
            {"title": "", "content": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("errors", response.json())
        self.assertEqual(Analysis_articles.objects.count(), 0)

    def test_non_ajax_save_redirects_after_success(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("write-article"),
                self.build_payload(title="Redirected Article"),
            )

        self.assertRedirects(
            response,
            reverse("write-article"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Analysis_articles.objects.filter(
                title="Redirected Article",
            ).exists()
        )

    def test_article_save_invalidates_without_rebuilding_homepage(self):
        cache.set(HOMEPAGE_SUMMARY_CACHE_KEY, {"cached": True}, 60)

        with patch("App.signals.get_homepage_summary") as rebuild:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("write-article"),
                    self.build_payload(title="Lazy Homepage Article"),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        self.assertEqual(response.status_code, 200)
        rebuild.assert_not_called()
        self.assertIsNone(cache.get(HOMEPAGE_SUMMARY_CACHE_KEY))
