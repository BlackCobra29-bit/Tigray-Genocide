import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import Administrator, Photo_archive, Tigray_woreda


class PhotoArchiveManagementPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="photo-management-superuser",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        cls.denied_user = user_model.objects.create_user(
            username="photo-management-denied",
            password="password",
        )
        cls.authors = [
            user_model.objects.create_user(
                username=f"photo-management-author-{index}",
                first_name="Archive",
                last_name=f"Author {index}",
            )
            for index in range(3)
        ]
        Administrator.objects.create(user=cls.superuser)
        Administrator.objects.create(user=cls.denied_user)
        cls.woreda = Tigray_woreda.objects.create(
            woreda_name="Photo Management Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )

        now = timezone.now()
        Photo_archive.objects.bulk_create(
            [
                Photo_archive(
                    author=cls.authors[index % len(cls.authors)],
                    location=f"Photo archive location {index:02d}",
                    woreda=cls.woreda,
                    date_of_event=(now - timedelta(days=index)).date(),
                    description=(
                        f"Photo archive description {index:02d} "
                        f"https://example.com/archive/{index}"
                    ),
                    photo=f"photo_archive/photo-{index}.jpg",
                    graphic=index % 2 == 0,
                    date_created=now - timedelta(minutes=index),
                )
                for index in range(30)
            ]
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.superuser)

    @staticmethod
    def table_params(**overrides):
        params = {
            "draw": "4",
            "start": "0",
            "length": "10",
            "order[0][column]": "5",
            "order[0][dir]": "desc",
            "search[value]": "",
        }
        params.update(overrides)
        return params

    def test_page_renders_only_the_server_side_table_shell(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("manage-photo-archive"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Photo archive data management")
        self.assertContains(
            response,
            'id="photo-archive-management-table"',
        )
        self.assertContains(response, "serverSide: true")
        self.assertContains(response, "searchDelay: 250")
        self.assertContains(
            response,
            reverse("photo-archive-management-data"),
        )
        self.assertContains(response, "<tbody></tbody>")
        self.assertContains(response, 'id="photo-archive-delete-modal"')
        self.assertContains(response, 'id="photo-archive-delete-form"')
        self.assertNotContains(response, "Photo archive description 00")

        sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("FROM `APP_PHOTO_ARCHIVE`", sql)
        self.assertLessEqual(len(queries), 5)

    def test_page_loads_only_required_table_assets(self):
        response = self.client.get(reverse("manage-photo-archive"))
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            html.count("/static/admin_static/datatable/"),
            6,
        )
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertNotIn("parsley.min.js", html)
        self.assertNotIn("dataTables.buttons.min.js", html)
        self.assertNotIn("buttons.html5.min.js", html)
        self.assertNotIn("dataTables.fixedHeader.min.js", html)
        self.assertNotIn("dataTables.keyTable.min.js", html)
        self.assertNotIn("dataTables.scroller.min.js", html)
        self.assertNotIn("jszip.min.js", html)
        self.assertNotIn("pdfmake.min.js", html)
        self.assertNotIn("vfs_fonts.js", html)
        self.assertIn("dataTables.responsive.min.js", html)
        self.assertLessEqual(len(asset_urls), 20)

    def test_pending_count_is_reused_from_cache(self):
        self.client.get(reverse("manage-photo-archive"))

        with CaptureQueriesContext(connection) as warm_queries:
            response = self.client.get(reverse("manage-photo-archive"))

        self.assertEqual(response.status_code, 200)
        sql = " ".join(
            query["sql"] for query in warm_queries
        ).upper()
        self.assertNotIn("COUNT(", sql)

    def test_data_endpoint_paginates_without_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("photo-archive-management-data"),
                self.table_params(),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draw"], 4)
        self.assertEqual(payload["recordsTotal"], 30)
        self.assertEqual(payload["recordsFiltered"], 30)
        self.assertEqual(len(payload["data"]), 10)
        self.assertIn(
            "photo-archive-delete-trigger",
            payload["data"][0][0],
        )
        self.assertIn(
            "https://example.com/archive/0",
            payload["data"][0][4],
        )

        sql = " ".join(query["sql"] for query in queries).lower()
        self.assertNotIn("`app_photo_archive`.`photo`", sql)
        self.assertNotIn("`app_photo_archive`.`graphic`", sql)
        self.assertNotIn("`app_photo_archive`.`woreda_id`", sql)
        self.assertLessEqual(len(queries), 4)

    def test_data_endpoint_searches_and_caps_page_size(self):
        response = self.client.get(
            reverse("photo-archive-management-data"),
            self.table_params(
                length="1000",
                **{"search[value]": "location 07"},
            ),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(
            payload["data"][0][2],
            "Photo archive location 07",
        )

    def test_delete_is_post_only_and_uses_inline_endpoint(self):
        photo_archive = Photo_archive.objects.get(
            location="Photo archive location 00",
        )
        delete_url = reverse(
            "delete-photo-archive",
            args=[photo_archive.id],
        )

        get_response = self.client.get(delete_url)
        with self.captureOnCommitCallbacks(execute=True):
            post_response = self.client.post(delete_url)

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 200)
        self.assertIn(
            "Photo archive location 00 was deleted successfully.",
            post_response.json()["message"],
        )
        self.assertFalse(
            Photo_archive.objects.filter(id=photo_archive.id).exists()
        )

    def test_superuser_can_still_update_photo_archive(self):
        photo_archive = Photo_archive.objects.get(
            location="Photo archive location 02",
        )
        update_url = reverse(
            "update-photo-archive",
            args=[photo_archive.id],
        )

        get_response = self.client.get(update_url)
        with self.captureOnCommitCallbacks(execute=True):
            post_response = self.client.post(
                update_url,
                {
                    "location": "Updated photo archive location",
                    "woreda": self.woreda.woreda_name,
                    "date_of_event": "2021-03-04",
                    "description": "Updated photo archive description",
                    "graphic": "on",
                },
            )

        self.assertEqual(get_response.status_code, 200)
        self.assertRedirects(
            post_response,
            reverse("manage-photo-archive"),
            fetch_redirect_response=False,
        )
        photo_archive.refresh_from_db()
        self.assertEqual(
            photo_archive.location,
            "Updated photo archive location",
        )
        self.assertEqual(
            photo_archive.description,
            "Updated photo archive description",
        )
        self.assertTrue(photo_archive.graphic)

    def test_non_superuser_cannot_manage_update_or_delete(self):
        photo_archive = Photo_archive.objects.get(
            location="Photo archive location 01",
        )
        self.client.force_login(self.denied_user)

        page_response = self.client.get(
            reverse("manage-photo-archive"),
        )
        data_response = self.client.get(
            reverse("photo-archive-management-data"),
            self.table_params(),
        )
        update_response = self.client.get(
            reverse(
                "update-photo-archive",
                args=[photo_archive.id],
            ),
        )
        delete_response = self.client.post(
            reverse(
                "delete-photo-archive",
                args=[photo_archive.id],
            ),
        )

        self.assertEqual(page_response.status_code, 403)
        self.assertEqual(data_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(
            Photo_archive.objects.filter(id=photo_archive.id).exists()
        )

    def test_photo_archive_date_created_has_database_index(self):
        index_names = {
            index.name
            for index in Photo_archive._meta.indexes
        }

        self.assertIn("photo_archive_created_idx", index_names)
