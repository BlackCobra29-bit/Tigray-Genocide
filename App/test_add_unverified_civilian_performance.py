import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Administrator, Tigray_woreda, Unverified_civilian


class AddUnverifiedCivilianPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="add-unverified-superuser",
            password="dashboard-password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(
            user=cls.superuser,
            civilian_role=True,
        )
        cls.first_woreda = Tigray_woreda.objects.create(
            woreda_name="Unverified First Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )
        cls.second_woreda = Tigray_woreda.objects.create(
            woreda_name="Unverified Second Woreda",
            latitude="13.6",
            longitude="39.6",
            zone="Eastern Tigray",
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    def build_payload(self):
        return {
            "location": "Test Location",
            "number_of_civilian": "12",
            "perpetrator": "Killed by Ethiopian forces",
            "woreda": self.first_woreda.woreda_name,
            "source": "Test Source",
            "source_link": "https://example.com/source",
            "remark": "Test remark",
        }

    def test_get_page_loads_only_the_assets_needed_by_the_form(self):
        response = self.client.get(reverse("add-unverified-civilian"))
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/static/froala_editor/", html)
        self.assertNotIn("/static/admin/js/vendor/jquery/jquery.js", html)
        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn("ajax.googleapis.com/ajax/libs/jquery", html)
        self.assertNotIn("Spinner-loading.gif", html)
        self.assertContains(response, "unverified-submit-spinner")
        self.assertEqual(html.count("/static/js/select.js"), 1)
        self.assertEqual(html.count("sweetalert2@10"), 1)
        self.assertEqual(html.count("parsley.min.js"), 1)
        self.assertLessEqual(len(asset_urls), 20)
        self.assertLess(len(response.content), 40_000)

    def test_woreda_options_are_rendered_from_the_cached_name_list(self):
        response = self.client.get(reverse("add-unverified-civilian"))
        html = response.content.decode()

        self.assertEqual(
            html.count(f'value="{self.first_woreda.woreda_name}"'),
            1,
        )
        self.assertEqual(
            html.count(f'value="{self.second_woreda.woreda_name}"'),
            1,
        )

    def test_get_page_reuses_cached_counts_and_woreda_names(self):
        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(
                reverse("add-unverified-civilian")
            )

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(
                reverse("add-unverified-civilian")
            )

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertLessEqual(len(cold_queries), 6)
        self.assertLessEqual(len(warm_queries), 3)

    def test_ajax_submission_skips_get_only_context_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                reverse("add-unverified-civilian"),
                self.build_payload(),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Success!")
        saved = Unverified_civilian.objects.get(location="Test Location")
        self.assertEqual(saved.woreda, self.first_woreda)
        self.assertEqual(saved.zone, self.first_woreda.zone)
        self.assertEqual(saved.number_of_civilian, 12)
        self.assertLessEqual(len(queries), 5)

        sql = " ".join(query["sql"] for query in queries)
        self.assertNotIn("COUNT(", sql.upper())
        self.assertNotIn("App_administrator", sql)
