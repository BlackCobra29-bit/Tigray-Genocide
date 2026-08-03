import re
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Administrator, Civilian_victims, Tigray_woreda


class AddCivilianVictimPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="add-civilian-superuser",
            password="dashboard-password",
            is_staff=True,
            is_superuser=True,
        )
        Administrator.objects.create(
            user=cls.superuser,
            civilian_role=True,
        )
        cls.first_woreda = Tigray_woreda.objects.create(
            woreda_name="Add Form First Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )
        cls.second_woreda = Tigray_woreda.objects.create(
            woreda_name="Add Form Second Woreda",
            latitude="13.6",
            longitude="39.6",
            zone="Eastern Tigray",
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    def build_payload(self, **updates):
        payload = {
            "fullname": "New Civilian Victim",
            "gender": "Male",
            "age": "35",
            "perpetrator": "Killed by Ethiopian forces",
            "place": "Test Place",
            "woreda": self.first_woreda.woreda_name,
            "source_link": "https://example.com/source",
            "source": "Test Source",
            "date_of_event": "2021-01-01",
            "remark": "Test remark",
        }
        payload.update(updates)
        return payload

    def test_unauthenticated_request_uses_the_real_login_route(self):
        response = Client().get(reverse("admin-add-civilian"))
        redirect_url = urlsplit(response["Location"])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(redirect_url.path, settings.LOGIN_URL)
        self.assertIn("authentication_required=", redirect_url.query)
        self.assertNotIn("Administrator-login-page", response["Location"])

    def test_get_page_uses_only_the_assets_needed_by_the_form(self):
        response = self.client.get(reverse("admin-add-civilian"))
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/static/admin/js/vendor/jquery/jquery.js", html)
        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn(
            "ajax.googleapis.com/ajax/libs/jquery",
            html,
        )
        self.assertEqual(html.count("/static/js/select.js"), 1)
        self.assertNotIn("sweetalert2", html)
        self.assertEqual(html.count("notyf@3"), 2)
        self.assertContains(response, "admin-feedback.js")
        self.assertContains(response, "Spinner-loading.gif")
        self.assertEqual(html.count("parsley.min.js"), 1)
        self.assertLessEqual(len(asset_urls), 23)
        self.assertLess(len(response.content), 40_000)

    def test_woreda_options_are_rendered_once(self):
        response = self.client.get(reverse("admin-add-civilian"))
        html = response.content.decode()

        self.assertEqual(
            html.count(f'value="{self.first_woreda.woreda_name}"'),
            1,
        )
        self.assertEqual(
            html.count(f'value="{self.second_woreda.woreda_name}"'),
            1,
        )
        self.assertNotIn(".selectpicker').empty()", html)
        self.assertNotIn(".selectpicker('refresh')", html)

    def test_get_page_reuses_cached_counts_and_woreda_names(self):
        with CaptureQueriesContext(connection) as cold_queries:
            cold_response = self.client.get(reverse("admin-add-civilian"))

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(reverse("admin-add-civilian"))

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertLessEqual(len(cold_queries), 6)
        self.assertLessEqual(len(warm_queries), 3)

    def test_ajax_submission_uses_the_request_user_and_bounded_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(
                reverse("admin-add-civilian"),
                self.build_payload(),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Success!")
        victim = Civilian_victims.objects.get(
            full_name="New Civilian Victim",
            woreda=self.first_woreda,
        )
        self.assertEqual(victim.author, self.superuser)
        self.assertTrue(victim.approval)
        self.assertLessEqual(len(queries), 6)

    def test_duplicate_detection_uses_the_exact_name_and_woreda_pair(self):
        existing_victim = Civilian_victims.objects.create(
            author=self.superuser,
            full_name="Exact Duplicate Victim",
            gender="Male",
            perpetrator="Killed by Ethiopian forces",
            woreda=self.first_woreda,
            zone=self.first_woreda.zone,
            approval=True,
        )

        response = self.client.post(
            reverse("admin-add-civilian"),
            self.build_payload(fullname=existing_victim.full_name),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIn(str(existing_victim.id), payload["message"])
        self.assertNotEqual(
            str(existing_victim.id),
            str(payload["new_duplicate_id"]),
        )
        self.assertEqual(
            Civilian_victims.objects.filter(
                full_name=existing_victim.full_name,
                woreda=self.first_woreda,
            ).count(),
            2,
        )

    def test_name_and_woreda_existing_on_different_rows_is_not_a_duplicate(self):
        Civilian_victims.objects.create(
            author=self.superuser,
            full_name="Shared Name",
            gender="Male",
            perpetrator="Killed by Ethiopian forces",
            woreda=self.first_woreda,
            zone=self.first_woreda.zone,
            approval=True,
        )
        Civilian_victims.objects.create(
            author=self.superuser,
            full_name="Different Name",
            gender="Male",
            perpetrator="Killed by Ethiopian forces",
            woreda=self.second_woreda,
            zone=self.second_woreda.zone,
            approval=True,
        )

        response = self.client.post(
            reverse("admin-add-civilian"),
            self.build_payload(
                fullname="Shared Name",
                woreda=self.second_woreda.woreda_name,
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Civilian_victims.objects.filter(
                full_name="Shared Name",
                woreda=self.second_woreda,
            ).exists()
        )

    def test_woreda_cache_is_invalidated_when_a_woreda_changes(self):
        self.client.get(reverse("admin-add-civilian"))

        with self.captureOnCommitCallbacks(execute=True):
            Tigray_woreda.objects.create(
                woreda_name="Newly Added Cached Woreda",
                latitude="13.7",
                longitude="39.7",
                zone="Southern Tigray",
            )

        response = self.client.get(reverse("admin-add-civilian"))

        self.assertContains(
            response,
            '<option value="Newly Added Cached Woreda">'
            "Newly Added Cached Woreda</option>",
            html=False,
        )

    def test_duplicate_lookup_has_a_composite_index(self):
        index_fields = {
            tuple(index.fields)
            for index in Civilian_victims._meta.indexes
        }

        self.assertIn(("full_name", "woreda"), index_fields)
