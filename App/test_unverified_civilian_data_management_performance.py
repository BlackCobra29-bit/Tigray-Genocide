from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import Resolver404, resolve, reverse

from .models import Administrator, Tigray_woreda, Unverified_civilian


class UnverifiedCivilianDataManagementPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="unverified-management-superuser",
            password="dashboard-password",
            is_staff=True,
            is_superuser=True,
        )
        cls.denied_user = user_model.objects.create_user(
            username="unverified-management-denied",
            password="dashboard-password",
            is_staff=True,
        )
        Administrator.objects.create(
            user=cls.superuser,
            civilian_role=True,
        )
        Administrator.objects.create(user=cls.denied_user)

        cls.woreda = Tigray_woreda.objects.create(
            woreda_name="Unverified Management Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )
        Unverified_civilian.objects.bulk_create(
            [
                Unverified_civilian(
                    location=f"Unverified Managed Location {index:02}",
                    number_of_civilian=index + 1,
                    perpetrator="Killed by Ethiopian forces",
                    woreda=cls.woreda,
                    zone=cls.woreda.zone,
                    source=f"Management Source {index:02}",
                    source_link=f"https://example.com/source/{index}",
                    remark=f"See https://example.com/remark/{index}",
                )
                for index in range(35)
            ]
        )

    def setUp(self):
        cache.clear()

    def test_page_renders_only_the_server_side_table_shell(self):
        self.client.force_login(self.superuser)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("unverified-civilian-data-management")
            )

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="unverified-civilian-management-table"',
        )
        self.assertContains(response, "serverSide: true")
        self.assertContains(response, "searchDelay: 250")
        self.assertContains(
            response,
            reverse("unverified-civilian-data-management-data"),
        )
        self.assertNotContains(response, "Unverified Managed Location 00")
        self.assertIn("<tbody></tbody>", html)
        self.assertLess(len(response.content), 50_000)
        self.assertLessEqual(len(queries), 6)

    def test_page_loads_only_the_lean_datatables_assets(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("unverified-civilian-data-management")
        )
        html = response.content.decode()

        self.assertNotIn("/static/admin/js/vendor/jquery/jquery.js", html)
        self.assertNotIn("/static/admin_static/js/parsley.min.js", html)
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn(
            "/static/admin_static/datatable/js/pdfmake.min.js",
            html,
        )
        self.assertNotIn(
            "/static/admin_static/datatable/js/vfs_fonts.js",
            html,
        )
        self.assertNotIn(
            "/static/admin_static/datatable/js/jszip.min.js",
            html,
        )
        self.assertEqual(
            html.count("/static/admin_static/datatable/"),
            6,
        )

    def test_management_page_has_lazy_legacy_export_buttons(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("unverified-civilian-data-management")
        )
        html = response.content.decode()

        self.assertContains(response, "Export current results:")
        self.assertEqual(html.count('data-export-format="'), 3)
        self.assertContains(response, 'data-export-format="pdf"')
        self.assertContains(response, 'data-export-format="csv"')
        self.assertContains(response, 'data-export-format="excel"')
        self.assertContains(response, "legacyExportScriptUrls")
        self.assertContains(response, "pageSize: 'TABLOID'")
        self.assertContains(response, "orientation: 'landscape'")
        self.assertContains(
            response,
            "title: 'Unidentified Civilian Victims'",
        )
        self.assertContains(response, "fillColor: '#23ffee'")
        self.assertContains(response, "doc.watermark")
        self.assertContains(response, "doc.footer")
        self.assertContains(response, "doc.defaultStyle.font = 'nyala'")
        self.assertNotIn(
            '<script src="/static/admlte/datatable/'
            'dataTables.buttons.min.js"',
            html,
        )
        self.assertNotIn(
            '<script src="/static/admlte/datatable/pdfmake.min.js"',
            html,
        )
        self.assertNotIn(
            '<script src="/static/admlte/datatable/vfs_fonts.js"',
            html,
        )

    def test_endpoint_is_paginated_without_woreda_n_plus_one_queries(self):
        self.client.force_login(self.superuser)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("unverified-civilian-data-management-data"),
                {
                    "draw": 4,
                    "start": 0,
                    "length": 10,
                },
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["draw"], 4)
        self.assertEqual(payload["recordsTotal"], 35)
        self.assertEqual(payload["recordsFiltered"], 35)
        self.assertEqual(len(payload["data"]), 10)
        self.assertTrue(
            all(
                "Unverified Management Woreda" in row[4]
                for row in payload["data"]
            )
        )
        self.assertLessEqual(len(queries), 5)

    def test_endpoint_preserves_search_ordering_and_cell_formatting(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("unverified-civilian-data-management-data"),
            {
                "draw": 1,
                "start": 0,
                "length": 10,
                "search[value]": "Location 17",
                "order[0][column]": 1,
                "order[0][dir]": "asc",
            },
        )

        payload = response.json()
        row = payload["data"][0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(row[1], "Unverified Managed Location 17")
        self.assertIn(
            '<a href="https://example.com/source/17"',
            row[5],
        )
        self.assertEqual(row[6], "https://example.com/source/17")
        self.assertIn(
            '<a href="https://example.com/remark/17"',
            row[7],
        )

    def test_export_data_contains_all_currently_filtered_rows(self):
        self.client.force_login(self.superuser)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse(
                    "unverified-civilian-data-management-export-data"
                ),
                {
                    "search[value]": "Location 17",
                    "order[0][column]": 1,
                    "order[0][dir]": "asc",
                },
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(
            payload["data"][0][0:3],
            [1, "Unverified Managed Location 17", 18],
        )
        self.assertEqual(
            payload["data"][0][4],
            "Unverified Management Woreda",
        )
        self.assertLessEqual(len(queries), 3)

    def test_endpoint_rejects_non_superusers(self):
        self.client.force_login(self.denied_user)
        response = self.client.get(
            reverse("unverified-civilian-data-management-data"),
            {"draw": 1, "start": 0, "length": 10},
        )

        self.assertEqual(response.status_code, 403)

    def test_export_endpoint_rejects_non_superusers(self):
        self.client.force_login(self.denied_user)
        response = self.client.get(
            reverse("unverified-civilian-data-management-export-data")
        )

        self.assertEqual(response.status_code, 403)

    def test_delete_uses_the_management_page_modal_and_post_endpoint(self):
        victim = Unverified_civilian.objects.create(
            location="Modal Delete Location",
            number_of_civilian=2,
            perpetrator="Killed by Ethiopian forces",
            woreda=self.woreda,
            zone=self.woreda.zone,
            source="Delete test source",
        )
        delete_url = reverse(
            "delete-unverified-civilian-victim",
            args=[victim.pk],
        )
        self.client.force_login(self.superuser)

        page_response = self.client.get(
            reverse("unverified-civilian-data-management")
        )
        data_response = self.client.get(
            reverse("unverified-civilian-data-management-data"),
            {
                "draw": 1,
                "start": 0,
                "length": 10,
                "search[value]": victim.location,
            },
        )
        get_delete_response = self.client.get(delete_url)
        post_delete_response = self.client.post(
            delete_url,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertNotContains(page_response, 'id="unverified-delete-modal"')
        self.assertContains(page_response, "admin-feedback.js")
        self.assertContains(page_response, "Spinner-loading.gif")
        action_cell = data_response.json()["data"][0][0]
        self.assertIn("unverified-delete-trigger admin-delete-trigger", action_cell)
        self.assertIn(f'data-delete-url="{delete_url}"', action_cell)
        self.assertEqual(get_delete_response.status_code, 405)
        self.assertEqual(post_delete_response.status_code, 200)
        self.assertFalse(
            Unverified_civilian.objects.filter(pk=victim.pk).exists()
        )

    def test_delete_endpoint_rejects_non_superusers(self):
        victim = Unverified_civilian.objects.create(
            location="Protected Delete Location",
            number_of_civilian=1,
            perpetrator="Killed by Ethiopian forces",
            woreda=self.woreda,
            zone=self.woreda.zone,
            source="Protected source",
        )
        self.client.force_login(self.denied_user)

        response = self.client.post(
            reverse(
                "delete-unverified-civilian-victim",
                args=[victim.pk],
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Unverified_civilian.objects.filter(pk=victim.pk).exists()
        )

    def test_old_export_page_route_and_navigation_are_removed(self):
        self.client.force_login(self.superuser)

        with self.assertRaises(Resolver404):
            resolve("/export-unverified-data")

        response = self.client.get(
            reverse("unverified-civilian-data-management")
        )
        self.assertNotContains(response, "/export-unverified-data")
