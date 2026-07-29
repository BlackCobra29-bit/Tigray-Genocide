from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


class HomepagePayloadTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_homepage_uses_one_external_plotly_runtime(self):
        response = self.client.get(reverse("app-index"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            html.count("/static/vendor/plotly/plotly-basic-3.3.1.min.js"),
            1,
        )
        self.assertEqual(html.count("Plotly.newPlot"), 2)
        self.assertNotIn("plotly.js v", html)

    def test_homepage_html_stays_below_payload_budget(self):
        response = self.client.get(reverse("app-index"))

        self.assertLess(len(response.content), 200_000)

    def test_homepage_is_browser_cacheable_for_five_minutes(self):
        response = self.client.get(reverse("app-index"))

        self.assertEqual(response["Cache-Control"], "max-age=300")
