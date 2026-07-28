from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .dashboard_summary import get_admin_dashboard_summary
from .models import Administrator, Civilian_victims, Unverified_civilian


class AdminDashboardPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="dashboard-admin",
            password="dashboard-password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(user=self.user)
        Civilian_victims.objects.create(
            full_name="Dashboard Victim",
            gender="Female",
            age=28,
            zone="Central Tigray",
            perpetrator="Killed by Eritrean forces",
            approval=True,
        )
        Unverified_civilian.objects.create(
            location="Dashboard Location",
            number_of_civilian=4,
            perpetrator="Killed by Eritrean forces",
            zone="Central Tigray",
            source="Dashboard Source",
        )
        self.client.force_login(self.user)
        cache.clear()

    def test_dashboard_summary_uses_grouped_queries(self):
        with CaptureQueriesContext(connection) as queries:
            summary = get_admin_dashboard_summary(force=True)

        self.assertEqual(summary["count_civilian"], 1)
        self.assertEqual(summary["line_data_points"][2], 5)
        self.assertLessEqual(len(queries), 10)

    def test_dashboard_reuses_cached_summary(self):
        first_response = self.client.get(reverse("admin-dashboard"))

        with CaptureQueriesContext(connection) as queries:
            second_response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            first_response.context["count_civilian"],
            second_response.context["count_civilian"],
        )
        self.assertLessEqual(len(queries), 3)

    def test_dashboard_uses_one_lightweight_plotly_runtime(self):
        response = self.client.get(reverse("admin-dashboard"))
        html = response.content.decode()

        self.assertEqual(
            html.count("/static/vendor/plotly/plotly-basic-3.3.1.min.js"),
            1,
        )
        self.assertEqual(html.count("Plotly.newPlot"), 2)
        self.assertNotIn("plotly.js v", html)
        self.assertNotIn("/static/js/plotly-api.js", html)

    def test_dashboard_does_not_load_unused_admin_libraries(self):
        response = self.client.get(reverse("admin-dashboard"))
        html = response.content.decode()

        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn("/static/admin/js/vendor/jquery/jquery.js", html)
        self.assertNotIn("/static/admin_static/js/parsley.min.js", html)
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertEqual(
            html.count("/static/admin_static/js/jquery.min.js"),
            1,
        )

    def test_dashboard_html_stays_below_payload_budget(self):
        response = self.client.get(reverse("admin-dashboard"))

        self.assertLess(len(response.content), 200_000)

    def test_dashboard_cache_is_invalidated_when_data_changes(self):
        first_response = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(first_response.context["count_civilian"], 1)

        with self.captureOnCommitCallbacks(execute=True):
            Civilian_victims.objects.create(
                full_name="New Dashboard Victim",
                gender="Male",
                zone="Eastern Tigray",
                perpetrator="Killed by Ethiopian forces",
                approval=True,
            )

        refreshed_response = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(refreshed_response.context["count_civilian"], 2)
