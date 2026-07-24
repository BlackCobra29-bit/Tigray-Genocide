import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Civilian_victims, Tigray_woreda


TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PublicPerformanceViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(username='author', password='password')
        self.woreda = Tigray_woreda.objects.create(
            woreda_name='Mekelle',
            latitude='13.5',
            longitude='39.5',
            zone='Mekelle Special',
        )

    def _create_victim(self, index):
        image = SimpleUploadedFile(
            f'victim-{index}.jpg',
            b'filecontent',
            content_type='image/jpeg',
        )
        return Civilian_victims.objects.create(
            author=self.user,
            full_name=f'Victim {index:02d}',
            gender='Male',
            woreda=self.woreda,
            zone='Mekelle Special',
            perpetrator='Killed by Ethiopian forces',
            source='Source',
            source_link='https://example.com',
            picture=image,
            approval=True,
        )

    def test_verified_victims_page_uses_server_side_pagination(self):
        for index in range(15):
            self._create_victim(index)

        response = self.client.get(reverse('civilian_victims_by_name'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['civilian_victims']), 10)
        self.assertContains(response, 'Page 1 of 2')
        self.assertContains(response, 'Victim 14')
        self.assertNotContains(response, 'Victim 00', html=False)

    def test_verified_victims_htmx_returns_partial(self):
        for index in range(12):
            self._create_victim(index)

        response = self.client.get(
            reverse('civilian_victims_by_name'),
            {'page': 2},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<html', html=False)
        self.assertNotContains(response, '<main id="main">', html=False)
        self.assertContains(response, 'Page 2 of 2')

    def test_victim_photo_load_more_returns_batch_markup(self):
        for index in range(35):
            self._create_victim(index)

        response = self.client.get(
            reverse('civilian-victim-photo-page'),
            {'page': 2, 'append': 1},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<html', html=False)
        self.assertNotContains(response, '<main id="main">', html=False)
        self.assertContains(response, 'victim-photo-load-more')
