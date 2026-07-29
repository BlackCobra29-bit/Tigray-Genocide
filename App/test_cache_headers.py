from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from tigray_genocide.cache_headers import (
    MEDIA_CACHE_SECONDS,
    ONE_YEAR_SECONDS,
    MediaCacheControlMiddleware,
    add_whitenoise_cache_headers,
)


class StaticCacheHeaderTests(SimpleTestCase):
    def test_fingerprinted_static_asset_is_immutable_for_one_year(self):
        headers = {}

        add_whitenoise_cache_headers(
            headers,
            "/srv/static/css/main.0123456789ab.css",
            "/static/css/main.0123456789ab.css",
        )

        self.assertEqual(
            headers["Cache-Control"],
            f"public, max-age={ONE_YEAR_SECONDS}, immutable",
        )

    def test_non_fingerprinted_static_asset_keeps_whitenoise_policy(self):
        headers = {"Cache-Control": "public, max-age=604800"}

        add_whitenoise_cache_headers(
            headers,
            "/srv/static/css/main.css",
            "/static/css/main.css",
        )

        self.assertEqual(
            headers["Cache-Control"],
            "public, max-age=604800",
        )


class MediaCacheHeaderTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()

    def get_response(self, path, method="get", response=None):
        middleware = MediaCacheControlMiddleware(
            lambda request: response or HttpResponse("media")
        )
        request = getattr(self.requests, method)(path)
        return middleware(request)

    def test_fingerprinted_media_is_immutable_for_one_year(self):
        response = self.get_response(
            "/media/photo/optimized/example.0123456789ab.800w.webp"
        )

        self.assertEqual(
            response["Cache-Control"],
            f"public, max-age={ONE_YEAR_SECONDS}, immutable",
        )

    def test_non_fingerprinted_media_is_cached_for_seven_days(self):
        response = self.get_response("/media/photo/example.webp")

        self.assertEqual(
            response["Cache-Control"],
            f"public, max-age={MEDIA_CACHE_SECONDS}",
        )

    def test_private_media_response_is_not_overridden(self):
        original_response = HttpResponse("private")
        original_response["Cache-Control"] = "private, no-store"

        response = self.get_response(
            "/media/private/example.webp",
            response=original_response,
        )

        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_non_media_response_is_not_modified(self):
        response = self.get_response("/Articles-page/")

        self.assertNotIn("Cache-Control", response)
