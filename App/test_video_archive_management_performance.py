import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import Administrator, Tigray_woreda, Video_archive
from .views import Update_video_archive


class VideoArchiveManagementPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="video-management-superuser",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        cls.denied_user = user_model.objects.create_user(
            username="video-management-denied",
            password="password",
        )
        cls.authors = [
            user_model.objects.create_user(
                username=f"video-management-author-{index}",
                first_name="Archive",
                last_name=f"Video Author {index}",
            )
            for index in range(3)
        ]
        Administrator.objects.create(user=cls.superuser)
        Administrator.objects.create(user=cls.denied_user)
        cls.woreda = Tigray_woreda.objects.create(
            woreda_name="Video Management Woreda",
            latitude="13.5",
            longitude="39.5",
            zone="Central Tigray",
        )

        now = timezone.now()
        Video_archive.objects.bulk_create(
            [
                Video_archive(
                    author=cls.authors[index % len(cls.authors)],
                    location=f"Video archive location {index:02d}",
                    woreda=cls.woreda,
                    date_of_event=(now - timedelta(days=index)).date(),
                    description=f"Video archive description {index:02d}",
                    online_link=f"https://example.com/video/{index}",
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
            "draw": "5",
            "start": "0",
            "length": "10",
            "order[0][column]": "5",
            "order[0][dir]": "desc",
            "search[value]": "",
        }
        params.update(overrides)
        return params

    def test_page_renders_only_server_side_table_shell(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("manage-video-archive"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Video archive data management")
        self.assertContains(
            response,
            'id="video-archive-management-table"',
        )
        self.assertContains(response, "serverSide: true")
        self.assertContains(response, "searchDelay: 250")
        self.assertContains(
            response,
            reverse("video-archive-management-data"),
        )
        self.assertContains(response, "<tbody></tbody>")
        self.assertContains(response, 'id="video-archive-delete-modal"')
        self.assertContains(response, 'id="video-archive-delete-form"')
        self.assertNotContains(response, "Video archive description 00")

        sql = " ".join(query["sql"] for query in queries).upper()
        self.assertNotIn("FROM `APP_VIDEO_ARCHIVE`", sql)
        self.assertLessEqual(len(queries), 5)

    def test_page_loads_only_required_table_assets(self):
        response = self.client.get(reverse("manage-video-archive"))
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
        self.client.get(reverse("manage-video-archive"))

        with CaptureQueriesContext(connection) as warm_queries:
            response = self.client.get(reverse("manage-video-archive"))

        self.assertEqual(response.status_code, 200)
        sql = " ".join(
            query["sql"] for query in warm_queries
        ).upper()
        self.assertNotIn("COUNT(", sql)

    def test_data_endpoint_paginates_without_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("video-archive-management-data"),
                self.table_params(),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draw"], 5)
        self.assertEqual(payload["recordsTotal"], 30)
        self.assertEqual(payload["recordsFiltered"], 30)
        self.assertEqual(len(payload["data"]), 10)
        self.assertIn(
            "video-archive-delete-trigger",
            payload["data"][0][0],
        )
        self.assertEqual(
            payload["data"][0][4],
            "Video archive description 00",
        )

        sql = " ".join(query["sql"] for query in queries).lower()
        self.assertNotIn("`app_video_archive`.`online_link`", sql)
        self.assertNotIn("`app_video_archive`.`woreda_id`", sql)
        self.assertLessEqual(len(queries), 4)

    def test_data_endpoint_searches_and_caps_page_size(self):
        response = self.client.get(
            reverse("video-archive-management-data"),
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
            "Video archive location 07",
        )

    def test_delete_is_post_only_and_uses_inline_endpoint(self):
        video_archive = Video_archive.objects.get(
            location="Video archive location 00",
        )
        delete_url = reverse(
            "delete-video-archive",
            args=[video_archive.id],
        )

        get_response = self.client.get(delete_url)
        with self.captureOnCommitCallbacks(execute=True):
            post_response = self.client.post(delete_url)

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 200)
        self.assertIn(
            "Video archive location 00 was deleted successfully.",
            post_response.json()["message"],
        )
        self.assertFalse(
            Video_archive.objects.filter(id=video_archive.id).exists()
        )

    def test_update_page_uses_cached_woredas_and_only_form_assets(self):
        video_archive = Video_archive.objects.get(
            location="Video archive location 02",
        )
        update_url = reverse(
            "update-video-archive",
            args=[video_archive.id],
        )

        cold_response = self.client.get(update_url)
        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(update_url)

        html = warm_response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(cold_response.status_code, 200)
        self.assertEqual(warm_response.status_code, 200)
        self.assertNotIn("/static/admin_static/datatable/", html)
        self.assertNotIn("/static/js/select.js", html)
        self.assertNotIn("/static/css/select.css", html)
        self.assertEqual(html.count("parsley.min.js"), 1)
        self.assertNotIn('enctype="multipart/form-data"', html)
        self.assertContains(warm_response, "Date of Event: (<i>optional</i>)")
        self.assertEqual(
            html.count(f'value="{self.woreda.woreda_name}"'),
            1,
        )
        self.assertContains(
            warm_response,
            f'value="{self.woreda.woreda_name}" selected',
        )
        self.assertLessEqual(len(asset_urls), 20)
        self.assertLessEqual(len(warm_queries), 4)

        warm_sql = " ".join(
            query["sql"] for query in warm_queries
        ).upper()
        self.assertNotIn("COUNT(", warm_sql)
        self.assertNotIn("APP_TIGRAY_WOREDA", warm_sql)

    def test_invalid_update_displays_errors_and_preserves_record(self):
        video_archive = Video_archive.objects.get(
            location="Video archive location 03",
        )
        update_url = reverse(
            "update-video-archive",
            args=[video_archive.id],
        )

        response = self.client.post(
            update_url,
            {
                "location": "Preserved video update location",
                "woreda": self.woreda.woreda_name,
                "date_of_event": "",
                "description": "Preserved invalid video description",
                "online_link": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("online_link", response.context["form"].errors)
        self.assertContains(response, "This field is required.")
        self.assertContains(
            response,
            'value="Preserved video update location"',
        )
        self.assertContains(
            response,
            "Preserved invalid video description",
        )
        self.assertContains(
            response,
            f'value="{self.woreda.woreda_name}" selected',
        )
        video_archive.refresh_from_db()
        self.assertEqual(
            video_archive.location,
            "Video archive location 03",
        )

    def test_update_uses_video_model_and_correct_heading(self):
        video_archive = Video_archive.objects.get(
            location="Video archive location 02",
        )
        update_url = reverse(
            "update-video-archive",
            args=[video_archive.id],
        )

        get_response = self.client.get(update_url)
        with self.captureOnCommitCallbacks(execute=True):
            post_response = self.client.post(
                update_url,
                {
                    "location": "Updated video archive location",
                    "woreda": self.woreda.woreda_name,
                    "date_of_event": "2021-03-04",
                    "description": "Updated video archive description",
                    "online_link": "https://example.com/video/updated",
                },
            )

        self.assertIs(Update_video_archive.model, Video_archive)
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(
            get_response,
            "Update video archive information",
        )
        self.assertNotContains(
            get_response,
            "Update photo archive information",
        )
        self.assertRedirects(
            post_response,
            reverse("manage-video-archive"),
            fetch_redirect_response=False,
        )
        video_archive.refresh_from_db()
        self.assertEqual(
            video_archive.location,
            "Updated video archive location",
        )
        self.assertEqual(
            video_archive.online_link,
            "https://example.com/video/updated",
        )

    def test_non_superuser_cannot_manage_update_or_delete(self):
        video_archive = Video_archive.objects.get(
            location="Video archive location 01",
        )
        self.client.force_login(self.denied_user)

        page_response = self.client.get(
            reverse("manage-video-archive"),
        )
        data_response = self.client.get(
            reverse("video-archive-management-data"),
            self.table_params(),
        )
        update_response = self.client.get(
            reverse(
                "update-video-archive",
                args=[video_archive.id],
            ),
        )
        delete_response = self.client.post(
            reverse(
                "delete-video-archive",
                args=[video_archive.id],
            ),
        )

        self.assertEqual(page_response.status_code, 403)
        self.assertEqual(data_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(
            Video_archive.objects.filter(id=video_archive.id).exists()
        )

    def test_video_archive_date_created_has_database_index(self):
        index_names = {
            index.name
            for index in Video_archive._meta.indexes
        }

        self.assertIn("video_archive_created_idx", index_names)
