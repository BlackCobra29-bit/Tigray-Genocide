import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .admin_metrics import ADMIN_PENDING_COUNT_CACHE_KEY
from .homepage import HOMEPAGE_SUMMARY_CACHE_KEY
from .models import Administrator, Civilian_victims, Tigray_woreda


class UpdateCivilianVictimPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username='civilian-update-manager',
            password='dashboard-password',
            is_staff=True,
        )
        cls.denied_user = user_model.objects.create_user(
            username='civilian-update-denied',
            password='dashboard-password',
            is_staff=True,
        )
        Administrator.objects.create(
            user=cls.manager,
            civilian_role=True,
        )
        Administrator.objects.create(user=cls.denied_user)
        cls.first_woreda = Tigray_woreda.objects.create(
            woreda_name='Update Form First Woreda',
            latitude='13.5',
            longitude='39.5',
            zone='Central Tigray',
        )
        cls.second_woreda = Tigray_woreda.objects.create(
            woreda_name='Update Form Second Woreda',
            latitude='13.6',
            longitude='39.6',
            zone='Eastern Tigray',
        )
        cls.victim = Civilian_victims.objects.create(
            author=cls.manager,
            full_name='Civilian Before Update',
            gender='Male',
            perpetrator='Killed by Ethiopian forces',
            woreda=cls.first_woreda,
            zone=cls.first_woreda.zone,
            source_link='https://example.com/original',
            approval=True,
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.manager)
        self.url = reverse(
            'update-civilian-victim',
            args=[self.victim.pk],
        )

    def build_payload(self, **updates):
        payload = {
            'sender_fullname': '',
            'sender_location': '',
            'sender_email': '',
            'sender_phone': '',
            'full_name': 'Civilian After Update',
            'gender': 'Male',
            'age': '35',
            'perpetrator': 'Killed by Ethiopian forces',
            'place_of_killing': 'Updated Place',
            'woreda': self.second_woreda.pk,
            'date_of_event': '2021-01-01',
            'source': 'Updated Source',
            'source_link': 'https://example.com/updated',
            'remark': 'Updated remark',
            'approval': '',
        }
        payload.update(updates)
        return payload

    def test_page_uses_only_form_assets(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        asset_urls = set(
            re.findall(
                r'<(?:script[^>]*src|link[^>]*href)="([^"]+)"',
                html,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('/static/admin/js/vendor/jquery/jquery.js', html)
        self.assertNotIn('/static/admin_static/datatable/', html)
        self.assertEqual(html.count('/static/js/select.js'), 1)
        self.assertEqual(html.count('parsley.min.js'), 1)
        self.assertLessEqual(len(asset_urls), 20)

    def test_warm_page_reuses_cached_counts_and_woreda_choices(self):
        self.client.get(self.url)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # Two authentication queries plus one Administrator and one victim
        # query. Cached counts and Woreda choices add no warm queries.
        self.assertLessEqual(len(queries), 4)
        self.assertTrue(cache.get(ADMIN_PENDING_COUNT_CACHE_KEY) is not None)

    def test_woreda_options_are_rendered_from_the_cached_list(self):
        response = self.client.get(self.url)

        self.assertContains(
            response,
            f'<option value="{self.first_woreda.pk}" selected>',
            html=False,
        )
        self.assertContains(
            response,
            f'<option value="{self.second_woreda.pk}">',
            html=False,
        )

    def test_role_is_enforced_before_get_and_post(self):
        self.client.force_login(self.denied_user)

        get_response = self.client.get(self.url)
        post_response = self.client.post(self.url, self.build_payload())

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.full_name, 'Civilian Before Update')

    def test_unauthenticated_user_is_redirected(self):
        response = Client().get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_update_uses_selected_woreda_without_a_second_lookup(self):
        self.client.get(self.url)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(self.url, self.build_payload())

        woreda_selects = [
            query['sql']
            for query in queries
            if 'FROM `App_tigray_woreda`' in query['sql']
            and query['sql'].lstrip().upper().startswith('SELECT')
        ]
        self.assertEqual(response.status_code, 302)
        self.assertLessEqual(
            len(woreda_selects),
            1,
            woreda_selects,
        )
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.woreda, self.second_woreda)
        self.assertEqual(self.victim.zone, self.second_woreda.zone)

    def test_hidden_approval_value_cannot_change_approval(self):
        response = self.client.post(
            self.url,
            self.build_payload(approval=''),
        )

        self.assertEqual(response.status_code, 302)
        self.victim.refresh_from_db()
        self.assertTrue(self.victim.approval)

    def test_civilian_update_invalidates_without_rebuilding_homepage(self):
        cache.set(HOMEPAGE_SUMMARY_CACHE_KEY, {'cached': True}, 300)

        with patch('App.signals.get_homepage_summary') as rebuild:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, self.build_payload())

        self.assertEqual(response.status_code, 302)
        rebuild.assert_not_called()
        self.assertIsNone(cache.get(HOMEPAGE_SUMMARY_CACHE_KEY))
