import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django_summernote.widgets import SummernoteWidget

from .forms import Webinar_discussion_Form
from .models import Administrator, Webinar


class WebinarSummernoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_user(
            username="webinar-manager",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(
            user=cls.superuser,
            analysis_role=True,
        )
        cls.webinar = Webinar.objects.create(
            author=cls.superuser,
            webinar_title="Existing panel",
            webinar_content="<p>Existing panel content</p>",
            webinar_video_url="https://example.com/panel",
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    def test_webinar_content_uses_text_storage_and_summernote_widget(self):
        model_field = Webinar._meta.get_field("webinar_content")
        form_field = Webinar_discussion_Form().fields["webinar_content"]

        self.assertIsInstance(model_field, models.TextField)
        self.assertIsInstance(form_field.widget, SummernoteWidget)

    def test_add_and_edit_pages_render_the_summernote_editor(self):
        add_response = self.client.get(reverse("add-webinar-discussion"))
        edit_response = self.client.get(
            reverse(
                "update-webinar-discussion",
                args=[self.webinar.pk],
            ),
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(
            add_response,
            "/summernote/editor/id_webinar_content/",
        )
        self.assertContains(
            edit_response,
            "/summernote/editor/id_webinar_content/",
        )

    def test_add_page_loads_only_the_assets_used_by_the_form(self):
        response = self.client.get(reverse("add-webinar-discussion"))
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
        self.assertContains(
            response,
            "/summernote/editor/id_webinar_content/",
        )
        self.assertLessEqual(len(asset_urls), 20)

    def test_add_page_reuses_the_cached_pending_count(self):
        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(
                reverse("add-webinar-discussion")
            )

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(
                reverse("add-webinar-discussion")
            )

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertLessEqual(len(cold_queries), 5)
        self.assertLessEqual(len(warm_queries), 3)
        warm_sql = " ".join(query["sql"] for query in warm_queries).upper()
        self.assertNotIn("COUNT(", warm_sql)

    def test_add_page_saves_summernote_html(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                reverse("add-webinar-discussion"),
                {
                    "webinar_title": "New panel",
                    "webinar_content": "<p>New panel content</p>",
                    "webinar_video_url": "",
                },
            )

        self.assertRedirects(
            response,
            reverse("add-webinar-discussion"),
            fetch_redirect_response=False,
        )
        created = Webinar.objects.get(webinar_title="New panel")
        self.assertEqual(created.author, self.superuser)
        self.assertEqual(
            created.webinar_content,
            "<p>New panel content</p>",
        )
        save_sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("COUNT(", save_sql)
        self.assertNotIn("APP_ADMINISTRATOR", save_sql)
        self.assertLessEqual(len(queries), 3)

    def test_invalid_add_preserves_values_and_displays_errors(self):
        response = self.client.post(
            reverse("add-webinar-discussion"),
            {
                "webinar_title": "Panel title to preserve",
                "webinar_content": "",
                "webinar_video_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel title to preserve")
        self.assertTrue(
            response.context["webinar_form"].errors["webinar_content"]
        )
        self.assertFalse(
            Webinar.objects.filter(
                webinar_title="Panel title to preserve",
            ).exists()
        )

    def test_authenticated_non_superuser_cannot_add_webinar(self):
        regular_user = get_user_model().objects.create_user(
            username="webinar-regular-user",
            password="password",
        )
        self.client.force_login(regular_user)

        response = self.client.post(
            reverse("add-webinar-discussion"),
            {
                "webinar_title": "Forbidden panel",
                "webinar_content": "<p>Forbidden content</p>",
                "webinar_video_url": "",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Webinar.objects.filter(
                webinar_title="Forbidden panel",
            ).exists()
        )

    def test_edit_page_saves_summernote_html(self):
        response = self.client.post(
            reverse(
                "update-webinar-discussion",
                args=[self.webinar.pk],
            ),
            {
                "webinar_title": "Updated panel",
                "webinar_content": "<p>Updated panel content</p>",
                "webinar_video_url": "https://example.com/updated-panel",
            },
        )

        self.assertRedirects(
            response,
            reverse("webinar-discussion-management"),
            fetch_redirect_response=False,
        )
        self.webinar.refresh_from_db()
        self.assertEqual(self.webinar.webinar_title, "Updated panel")
        self.assertEqual(
            self.webinar.webinar_content,
            "<p>Updated panel content</p>",
        )
