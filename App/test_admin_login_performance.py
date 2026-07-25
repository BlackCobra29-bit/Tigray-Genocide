from unittest.mock import patch

from captcha.models import CaptchaStore
from django.contrib.auth import get_user_model
from django.test import TestCase


class AdminLoginPerformanceTests(TestCase):
    login_url = "/Adminstrator-login-page/"

    @staticmethod
    def valid_captcha():
        key = CaptchaStore.generate_key()
        response = CaptchaStore.objects.get(hashkey=key).response
        return {"captcha_0": key, "captcha_1": response}

    def test_login_page_loads_only_its_small_stylesheet(self):
        response = self.client.get(self.login_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin_static/css/admin-login.css")
        self.assertNotContains(response, "bootstrap.min.css")
        self.assertNotContains(response, "all.min.css")
        self.assertNotContains(response, "custom.min.css")
        self.assertNotContains(response, "nprogress.css")
        self.assertNotContains(response, "parsley.min.js")

    @patch("App.views.authenticate")
    def test_invalid_captcha_is_rejected_before_authentication(self, authenticate):
        response = self.client.post(
            self.login_url,
            {
                "login_username": "automated-client",
                "login_password": "irrelevant",
                "captcha_0": "invalid-key",
                "captcha_1": "invalid-response",
            },
        )

        self.assertEqual(response.status_code, 200)
        authenticate.assert_not_called()
        self.assertContains(response, "Invalid CAPTCHA")

    @patch("App.views.authenticate")
    def test_valid_captcha_reaches_authentication(self, authenticate):
        authenticate.return_value = None
        payload = {
            "login_username": "unknown",
            "login_password": "wrong",
            **self.valid_captcha(),
        }

        response = self.client.post(self.login_url, payload)

        self.assertRedirects(response, self.login_url)
        authenticate.assert_called_once_with(username="unknown", password="wrong")

    def test_valid_login_still_uses_django_authentication(self):
        user = get_user_model().objects.create_user(
            username="administrator",
            password="secure-password",
        )
        payload = {
            "login_username": "administrator",
            "login_password": "secure-password",
            **self.valid_captcha(),
        }

        response = self.client.post(self.login_url, payload)

        self.assertRedirects(
            response,
            "/Admin-dashboard/",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.session.get("_auth_user_id"),
            str(user.pk),
        )

    def test_authenticated_request_does_not_create_an_unused_captcha(self):
        user = get_user_model().objects.create_user(
            username="already-signed-in",
            password="secure-password",
        )
        self.client.force_login(user)
        captcha_count = CaptchaStore.objects.count()

        response = self.client.get(self.login_url)

        self.assertRedirects(
            response,
            "/Admin-dashboard/",
            fetch_redirect_response=False,
        )
        self.assertEqual(CaptchaStore.objects.count(), captcha_count)
