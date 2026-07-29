import re

from django.conf import settings


ONE_YEAR_SECONDS = 31_536_000
MEDIA_CACHE_SECONDS = 604_800
FINGERPRINTED_ASSET_PATTERN = re.compile(r'\.[0-9a-f]{12}\.', re.IGNORECASE)


def is_fingerprinted_asset(url):
    """Return whether a URL contains the project's 12-character content hash."""
    return bool(FINGERPRINTED_ASSET_PATTERN.search(url))


def add_whitenoise_cache_headers(headers, path, url):
    """Give fingerprinted static assets an explicit one-year immutable policy."""
    if is_fingerprinted_asset(url):
        headers['Cache-Control'] = (
            f'public, max-age={ONE_YEAR_SECONDS}, immutable'
        )


class MediaCacheControlMiddleware:
    """Attach safe browser-cache headers to uploaded media responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        media_url = settings.MEDIA_URL
        if (
            request.method not in {'GET', 'HEAD'}
            or not request.path_info.startswith(media_url)
            or response.status_code not in {200, 206, 304}
        ):
            return response

        current_policy = response.get('Cache-Control', '').lower()
        if 'private' in current_policy or 'no-store' in current_policy:
            return response

        if is_fingerprinted_asset(request.path_info):
            response['Cache-Control'] = (
                f'public, max-age={ONE_YEAR_SECONDS}, immutable'
            )
        else:
            response['Cache-Control'] = (
                f'public, max-age={MEDIA_CACHE_SECONDS}'
            )

        return response
