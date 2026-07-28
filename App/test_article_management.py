from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Administrator, Analysis_articles


class ArticleManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_user(
            username="article-manager",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        cls.analyst = user_model.objects.create_user(
            username="article-analyst",
            password="password",
            first_name="Article",
            last_name="Analyst",
        )
        cls.denied_user = user_model.objects.create_user(
            username="article-denied",
            password="password",
        )
        Administrator.objects.create(
            user=cls.superuser,
            analysis_role=True,
        )
        Administrator.objects.create(
            user=cls.analyst,
            analysis_role=True,
        )
        Administrator.objects.create(user=cls.denied_user)

        cls.published_article = Analysis_articles.objects.create(
            author=cls.analyst,
            title="Published article",
            thumbnail="articles_thumbnail/published.png",
            content="<p>Published body</p>",
            approval=True,
            draft=False,
        )
        cls.pending_article = Analysis_articles.objects.create(
            author=cls.analyst,
            title="Pending article",
            thumbnail="articles_thumbnail/pending.png",
            content="<p>Pending body</p>",
            approval=False,
            draft=False,
        )
        cls.analyst_draft = Analysis_articles.objects.create(
            author=cls.analyst,
            title="Analyst draft",
            thumbnail="articles_thumbnail/analyst-draft.png",
            content="<p>Draft body</p>",
            approval=False,
            draft=True,
        )
        cls.manager_draft = Analysis_articles.objects.create(
            author=cls.superuser,
            title="Manager draft",
            thumbnail="articles_thumbnail/manager-draft.png",
            content="<p>Manager draft body</p>",
            approval=True,
            draft=True,
        )
        cls.legacy_published_article = Analysis_articles.objects.create(
            author=None,
            title="Legacy published article",
            thumbnail="articles_thumbnail/legacy.png",
            content="<p>Legacy body</p>",
            approval=True,
            draft=False,
        )

    def setUp(self):
        cache.clear()

    def test_page_renders_only_the_server_side_table_shell(self):
        self.client.force_login(self.superuser)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("analysis-article-management"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Article Management")
        self.assertContains(response, 'id="article-management-table"')
        self.assertContains(response, "serverSide: true")
        self.assertContains(response, "searchDelay: 250")
        self.assertContains(
            response,
            reverse("analysis-article-management-data"),
        )
        self.assertContains(response, "<tbody></tbody>")
        self.assertContains(response, 'id="article-delete-modal"')
        self.assertContains(response, 'id="article-delete-form"')
        self.assertNotContains(response, "Published article")
        self.assertNotContains(response, "Analyst draft")
        self.assertNotContains(response, "Pending article")
        self.assertLessEqual(len(queries), 5)

    def test_page_loads_only_the_required_datatables_assets(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("analysis-article-management"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            html.count("/static/admin_static/datatable/"),
            6,
        )
        self.assertNotIn("dataTables.buttons.min.js", html)
        self.assertNotIn("buttons.html5.min.js", html)
        self.assertNotIn("buttons.print.min.js", html)
        self.assertNotIn("dataTables.fixedHeader.min.js", html)
        self.assertNotIn("dataTables.keyTable.min.js", html)
        self.assertNotIn("dataTables.scroller.min.js", html)
        self.assertNotIn("jszip.min.js", html)
        self.assertNotIn("pdfmake.min.js", html)
        self.assertNotIn("vfs_fonts.js", html)

    def test_superuser_data_contains_published_articles_and_own_drafts(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("analysis-article-management-data"),
            {
                "draw": "3",
                "start": "0",
                "length": "10",
                "order[0][column]": "5",
                "order[0][dir]": "desc",
            },
        )
        payload = response.json()
        rows = payload["data"]
        titles = {row[3] for row in rows}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["draw"], 3)
        self.assertEqual(payload["recordsTotal"], 3)
        self.assertEqual(payload["recordsFiltered"], 3)
        self.assertEqual(
            titles,
            {
                "Published article",
                "Manager draft",
                "Legacy published article",
            },
        )
        self.assertTrue(any("Published" in row[1] for row in rows))
        self.assertTrue(any("Draft" in row[1] for row in rows))
        published_action = next(
            row[0] for row in rows if row[3] == "Published article"
        )
        self.assertIn('class="article-delete-trigger"', published_action)
        self.assertIn(
            reverse(
                "delete-analysis-article",
                args=[self.published_article.pk],
            ),
            published_action,
        )
        self.assertTrue(
            any(
                row[2] == "Unknown"
                for row in rows
                if row[3] == "Legacy published article"
            )
        )

    def test_analyst_data_contains_all_their_states_and_supports_search(self):
        self.client.force_login(self.analyst)
        data_url = reverse("analysis-article-management-data")

        response = self.client.get(
            data_url,
            {"draw": "1", "start": "0", "length": "2"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["recordsTotal"], 3)
        self.assertEqual(payload["recordsFiltered"], 3)
        self.assertEqual(len(payload["data"]), 2)

        response = self.client.get(
            data_url,
            {
                "draw": "2",
                "start": "0",
                "length": "10",
                "search[value]": "pending",
            },
        )
        payload = response.json()

        self.assertEqual(payload["recordsTotal"], 3)
        self.assertEqual(payload["recordsFiltered"], 1)
        self.assertEqual(payload["data"][0][3], "Pending article")
        self.assertIn("Pending approval", payload["data"][0][1])

    def test_data_endpoint_has_bounded_queries(self):
        self.client.force_login(self.analyst)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("analysis-article-management-data"),
                {"draw": "1", "start": "0", "length": "10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 5)

    def test_data_endpoint_rejects_users_without_analysis_role(self):
        self.client.force_login(self.denied_user)

        response = self.client.get(
            reverse("analysis-article-management-data"),
        )

        self.assertEqual(response.status_code, 403)

    def test_article_delete_endpoint_rejects_get_requests(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "delete-analysis-article",
                args=[self.published_article.pk],
            ),
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Analysis_articles.objects.filter(
                pk=self.published_article.pk,
            ).exists()
        )

    def test_superuser_deletes_article_without_confirmation_page(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse(
                "delete-analysis-article",
                args=[self.published_article.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["message"])
        self.assertFalse(
            Analysis_articles.objects.filter(
                pk=self.published_article.pk,
            ).exists()
        )

    def test_analyst_can_delete_only_their_own_draft(self):
        self.client.force_login(self.analyst)
        published_delete_url = reverse(
            "delete-analysis-article",
            args=[self.published_article.pk],
        )

        denied_response = self.client.post(published_delete_url)

        self.assertEqual(denied_response.status_code, 403)
        self.assertTrue(
            Analysis_articles.objects.filter(
                pk=self.published_article.pk,
            ).exists()
        )

        draft_response = self.client.post(
            reverse(
                "delete-analysis-article",
                args=[self.analyst_draft.pk],
            ),
        )

        self.assertEqual(draft_response.status_code, 200)
        self.assertFalse(
            Analysis_articles.objects.filter(
                pk=self.analyst_draft.pk,
            ).exists()
        )

    def test_user_without_analysis_role_cannot_delete_articles(self):
        self.client.force_login(self.denied_user)

        response = self.client.post(
            reverse(
                "delete-analysis-article",
                args=[self.analyst_draft.pk],
            ),
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Analysis_articles.objects.filter(
                pk=self.analyst_draft.pk,
            ).exists()
        )

    def test_legacy_draft_page_redirects_to_article_management(self):
        self.client.force_login(self.analyst)

        response = self.client.get(reverse("draft-article-management"))

        self.assertRedirects(
            response,
            reverse("analysis-article-management"),
            fetch_redirect_response=False,
        )

    def test_editing_a_draft_preserves_or_changes_its_status_by_button(self):
        self.client.force_login(self.analyst)
        edit_url = reverse(
            "update-draft-article",
            args=[self.analyst_draft.pk],
        )
        payload = {
            "title": self.analyst_draft.title,
            "content": self.analyst_draft.content,
            "save_draft": "true",
        }

        response = self.client.post(edit_url, payload)

        self.assertRedirects(
            response,
            reverse("analysis-article-management"),
            fetch_redirect_response=False,
        )
        self.analyst_draft.refresh_from_db()
        self.assertTrue(self.analyst_draft.draft)

        payload.pop("save_draft")
        payload["publish"] = "true"
        response = self.client.post(edit_url, payload)

        self.assertRedirects(
            response,
            reverse("analysis-article-management"),
            fetch_redirect_response=False,
        )
        self.analyst_draft.refresh_from_db()
        self.assertFalse(self.analyst_draft.draft)
