from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import Administrator, Webinar


class WebinarManagementPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="webinar-superuser",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        cls.denied_user = user_model.objects.create_user(
            username="webinar-denied",
            password="password",
        )
        cls.authors = [
            user_model.objects.create_user(
                username=f"webinar-author-{index}",
                first_name="Panel",
                last_name=f"Author {index}",
            )
            for index in range(3)
        ]
        Administrator.objects.create(
            user=cls.superuser,
            analysis_role=True,
        )
        Administrator.objects.create(
            user=cls.denied_user,
            analysis_role=True,
        )

        now = timezone.now()
        Webinar.objects.bulk_create(
            [
                Webinar(
                    author=cls.authors[index % len(cls.authors)],
                    webinar_title=f"Panel discussion {index:02d}",
                    webinar_content=(
                        f"<p>Large editor content that must not be loaded "
                        f"for row {index}</p>"
                    ),
                    webinar_video_url=(
                        f"https://example.com/panel/{index}"
                        if index % 2
                        else ""
                    ),
                    date_created=now - timedelta(minutes=index),
                )
                for index in range(30)
            ]
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    def table_params(self, **overrides):
        params = {
            "draw": "3",
            "start": "0",
            "length": "10",
            "order[0][column]": "4",
            "order[0][dir]": "desc",
            "search[value]": "",
        }
        params.update(overrides)
        return params

    def test_page_renders_only_the_server_side_table_shell(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("webinar-discussion-management"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel discussion Management")
        self.assertContains(response, 'id="webinar-management-table"')
        self.assertContains(response, "serverSide: true")
        self.assertContains(response, "searchDelay: 250")
        self.assertContains(
            response,
            reverse("webinar-discussion-management-data"),
        )
        self.assertContains(response, "<tbody></tbody>")
        self.assertContains(response, 'id="webinar-delete-modal"')
        self.assertContains(response, 'id="webinar-delete-form"')
        self.assertNotContains(response, "Panel discussion 00")

        sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("FROM `APP_WEBINAR`", sql)
        self.assertLessEqual(len(queries), 5)

    def test_page_loads_only_the_required_table_assets(self):
        response = self.client.get(
            reverse("webinar-discussion-management"),
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            html.count("/static/admin_static/datatable/"),
            8,
        )
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertNotIn("dataTables.buttons.min.js", html)
        self.assertNotIn("buttons.html5.min.js", html)
        self.assertNotIn("dataTables.keyTable.min.js", html)
        self.assertNotIn("dataTables.scroller.min.js", html)
        self.assertNotIn("jszip.min.js", html)
        self.assertNotIn("pdfmake.min.js", html)
        self.assertNotIn("vfs_fonts.js", html)
        self.assertIn("dataTables.fixedHeader.min.js", html)
        self.assertIn("dataTables.responsive.min.js", html)

    def test_pending_count_is_reused_from_cache(self):
        self.client.get(reverse("webinar-discussion-management"))

        with CaptureQueriesContext(connection) as warm_queries:
            response = self.client.get(
                reverse("webinar-discussion-management"),
            )

        self.assertEqual(response.status_code, 200)
        sql = " ".join(
            query["sql"] for query in warm_queries
        ).upper()
        self.assertNotIn("COUNT(", sql)

    def test_data_endpoint_paginates_without_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("webinar-discussion-management-data"),
                self.table_params(),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draw"], 3)
        self.assertEqual(payload["recordsTotal"], 30)
        self.assertEqual(payload["recordsFiltered"], 30)
        self.assertEqual(len(payload["data"]), 10)
        self.assertIn("webinar-delete-trigger", payload["data"][0][0])

        sql = " ".join(query["sql"] for query in queries)
        self.assertNotIn("webinar_content", sql.lower())
        self.assertLessEqual(len(queries), 4)

    def test_data_endpoint_searches_and_caps_page_size(self):
        response = self.client.get(
            reverse("webinar-discussion-management-data"),
            self.table_params(
                length="1000",
                **{"search[value]": "discussion 07"},
            ),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0][2], "Panel discussion 07")

    def test_delete_is_post_only_and_uses_the_inline_endpoint(self):
        webinar = Webinar.objects.get(
            webinar_title="Panel discussion 00",
        )
        delete_url = reverse(
            "delete-webinar-discussion",
            args=[webinar.id],
        )

        get_response = self.client.get(delete_url)
        post_response = self.client.post(delete_url)

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 200)
        self.assertIn(
            "Panel discussion 00 was deleted successfully.",
            post_response.json()["message"],
        )
        self.assertFalse(
            Webinar.objects.filter(id=webinar.id).exists()
        )

    def test_non_superuser_cannot_manage_update_or_delete(self):
        webinar = Webinar.objects.get(
            webinar_title="Panel discussion 01",
        )
        self.client.force_login(self.denied_user)

        page_response = self.client.get(
            reverse("webinar-discussion-management"),
        )
        data_response = self.client.get(
            reverse("webinar-discussion-management-data"),
            self.table_params(),
        )
        update_response = self.client.get(
            reverse(
                "update-webinar-discussion",
                args=[webinar.id],
            ),
        )
        delete_response = self.client.post(
            reverse(
                "delete-webinar-discussion",
                args=[webinar.id],
            ),
        )

        self.assertEqual(page_response.status_code, 403)
        self.assertEqual(data_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(
            Webinar.objects.filter(id=webinar.id).exists()
        )

    def test_webinar_date_created_has_a_database_index(self):
        index_names = {
            index.name
            for index in Webinar._meta.indexes
        }

        self.assertIn("webinar_created_idx", index_names)
