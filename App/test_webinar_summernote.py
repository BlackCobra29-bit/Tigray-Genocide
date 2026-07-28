from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
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

    def test_add_page_saves_summernote_html(self):
        response = self.client.post(
            reverse("add-webinar-discussion"),
            {
                "webinar_title": "New panel",
                "webinar_content": "<p>New panel content</p>",
                "webinar_video_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        created = Webinar.objects.get(webinar_title="New panel")
        self.assertEqual(created.author, self.superuser)
        self.assertEqual(
            created.webinar_content,
            "<p>New panel content</p>",
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
