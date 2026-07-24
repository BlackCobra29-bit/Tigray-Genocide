from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Civilian_victims, Photo_archive, Tigray_woreda, Unverified_civilian


class CivilianVictimsByNameTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        woreda = Tigray_woreda.objects.create(
            woreda_name='Test Woreda',
            latitude='0',
            longitude='0',
            zone='Test Zone',
        )
        Civilian_victims.objects.bulk_create([
            Civilian_victims(
                full_name=f'Victim {index:02d}',
                gender='Male',
                woreda=woreda,
                zone='Test Zone',
                perpetrator='Killed by Ethiopian forces',
                approval=True,
            )
            for index in range(25)
        ])

    def test_page_loads_only_ten_victims_with_bounded_queries(self):
        cache.delete('public_woreda_list')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('civilian_victims_by_name'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 10)
        self.assertEqual(response.context['total_count'], 25)
        self.assertEqual(len(queries), 3)

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(reverse('civilian_victims_by_name'))

        self.assertEqual(warm_response.status_code, 200)
        self.assertEqual(len(warm_queries), 2)

    def test_page_does_not_load_unused_shared_libraries(self):
        response = self.client.get(reverse('civilian_victims_by_name'))

        self.assertContains(response, 'htmx.org@1.9.12')
        self.assertContains(response, 'js/select.js')
        self.assertNotContains(response, 'js/chart.js')
        self.assertNotContains(response, 'glightbox.min')
        self.assertNotContains(response, 'swiper-bundle.min')
        self.assertNotContains(response, 'purecounter_vanilla.js')
        self.assertNotContains(response, 'jquery.dataTables.min.js')
        self.assertNotContains(response, 'parsley.min.js')
        self.assertNotContains(response, 'sweetalert.min.js')

    def test_filters_run_on_server_and_are_kept_in_pagination(self):
        response = self.client.get(
            reverse('civilian_victims_by_name'),
            {'name': 'Victim'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 25)
        self.assertEqual(len(response.context['page'].object_list), 10)
        self.assertContains(response, 'name=Victim&amp;page=2')

    def test_async_request_returns_only_the_results_fragment(self):
        response = self.client.get(
            reverse('civilian_victims_by_name'),
            {'page': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'public_partials/civilian_victim_results.html',
        )
        self.assertContains(response, 'Page 2 of 3')
        self.assertContains(response, 'data-async-page')
        self.assertNotContains(response, '<main')

    def test_boosted_navigation_returns_the_complete_public_page(self):
        response = self.client.get(
            reverse('civilian_victims_by_name'),
            HTTP_HX_REQUEST='true',
            HTTP_HX_BOOSTED='true',
        )

        self.assertTemplateUsed(response, 'civilian_victims_by_name.html')
        self.assertContains(response, 'id="page-content"')
        self.assertContains(response, 'id="page-assets"')
        self.assertContains(response, 'class="htmx-region"')


class CivilianVictimsByPhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        woreda = Tigray_woreda.objects.create(
            woreda_name='Photo Test Woreda',
            latitude='0',
            longitude='0',
            zone='Test Zone',
        )
        Civilian_victims.objects.bulk_create([
            Civilian_victims(
                full_name=f'Photo Victim {index:02d}',
                gender='Female',
                woreda=woreda,
                zone='Test Zone',
                perpetrator='Killed by Eritrean forces',
                approval=True,
            )
            for index in range(65)
        ])

    def test_initial_gallery_loads_only_thirty_cards(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('civilian-victim-photo-page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 30)
        self.assertEqual(response.context['filtered_count'], 65)
        self.assertContains(response, 'Load 30 more')
        self.assertContains(response, 'htmx.min.js')
        self.assertLessEqual(len(queries), 4)

    def test_htmx_load_more_returns_only_the_next_batch(self):
        response = self.client.get(
            reverse('civilian-victim-photo-page'),
            {'page': 2},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'public_partials/victim_photo_batch.html',
        )
        self.assertEqual(len(response.context['page'].object_list), 30)
        self.assertContains(response, 'page=3')
        self.assertNotContains(response, '<main')

    def test_htmx_filter_returns_only_the_gallery_fragment(self):
        response = self.client.get(
            reverse('civilian-victim-photo-page'),
            {'perpetrator': 'Killed by Eritrean forces'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'public_partials/victim_photo_grid.html',
        )
        self.assertContains(response, 'class="victim-photo-fragment"')
        self.assertContains(response, 'id="victim-photo-section"')
        self.assertNotContains(response, '<main')
        self.assertNotContains(response, 'class="breadcrumbs"')

    def test_boosted_navigation_does_not_return_a_gallery_batch(self):
        response = self.client.get(
            reverse('civilian-victim-photo-page'),
            HTTP_HX_REQUEST='true',
            HTTP_HX_BOOSTED='true',
        )

        self.assertTemplateUsed(response, 'civilin_vicitm_photo_page.html')
        self.assertContains(response, 'id="page-content"')
        self.assertContains(response, 'Loading victim gallery...')


class CivilianVictimsByLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.selected_woreda = Tigray_woreda.objects.create(
            woreda_name='Location Test Woreda',
            latitude='13.5',
            longitude='39.5',
            zone='Test Zone',
        )
        other_woreda = Tigray_woreda.objects.create(
            woreda_name='Other Test Woreda',
            latitude='14.0',
            longitude='39.0',
            zone='Test Zone',
        )
        Civilian_victims.objects.bulk_create([
            Civilian_victims(
                full_name=f'Location Victim {index:02d}',
                gender='Male',
                woreda=cls.selected_woreda,
                zone='Test Zone',
                perpetrator='Killed by Ethiopian forces',
                approval=True,
            )
            for index in range(30)
        ] + [
            Civilian_victims(
                full_name='Other Location Victim',
                gender='Female',
                woreda=other_woreda,
                zone='Test Zone',
                perpetrator='Killed by Eritrean forces',
                approval=True,
            )
        ])

    def setUp(self):
        cache.clear()

    def test_location_map_uses_one_aggregate_query(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('civilian-victim-map-page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Civilian Victims: 30')
        self.assertLessEqual(len(queries), 2)

    def test_location_detail_limits_table_to_twenty_five_rows(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse(
                    'civilian-victim-map-info-page',
                    args=['location-test-woreda'],
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['civilian_victims']), 25)
        self.assertEqual(response.context['page'].paginator.count, 30)
        self.assertContains(response, 'Page 1 of 2')
        self.assertLessEqual(len(queries), 4)


class UnidentifiedCivilianVictimsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        woreda = Tigray_woreda.objects.create(
            woreda_name='Unidentified Test Woreda',
            latitude='13.5',
            longitude='39.5',
            zone='Test Zone',
        )
        Unverified_civilian.objects.bulk_create([
            Unverified_civilian(
                location=f'Test Location {index:02d}',
                number_of_civilian=index + 1,
                perpetrator='Killed by Ethiopian forces',
                woreda=woreda,
                zone='Test Zone',
                source='Test source',
            )
            for index in range(25)
        ])

    def test_initial_page_loads_ten_records_with_bounded_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('unverified-civilian-victim'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 10)
        self.assertEqual(response.context['filtered_count'], 25)
        self.assertEqual(response.context['total_civilians'], 325)
        self.assertContains(response, 'id="datatable2"')
        self.assertLessEqual(len(queries), 4)

    def test_htmx_pagination_returns_only_results_in_two_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse('unverified-civilian-victim'),
                {'page': 2},
                HTTP_HX_REQUEST='true',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public_partials/unverified_results.html')
        self.assertEqual(len(response.context['page'].object_list), 10)
        self.assertContains(response, 'Page 2 of 3')
        self.assertNotContains(response, '<main')
        self.assertLessEqual(len(queries), 2)

    def test_boosted_navigation_returns_the_unidentified_page_shell(self):
        response = self.client.get(
            reverse('unverified-civilian-victim'),
            HTTP_HX_REQUEST='true',
            HTTP_HX_BOOSTED='true',
        )

        self.assertTemplateUsed(response, 'unverified_civilian_victim.html')
        self.assertContains(response, 'id="page-content"')
        self.assertContains(response, 'Loading victims...')


class SubmitVictimInformationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.woreda = Tigray_woreda.objects.create(
            woreda_name='Submission Test Woreda',
            latitude='13.5',
            longitude='39.5',
            zone='Test Zone',
        )

    def setUp(self):
        cache.delete('submission-form-woreda-names')

    def test_submission_page_contains_sender_and_victim_sections(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('send-information'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Civilian Victim Information Submission Form')
        self.assertContains(response, 'Sender Information')
        self.assertContains(response, 'Civilian Victim Information')
        self.assertContains(response, 'name="sender_fullname"')
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'parsley.min.js')
        self.assertContains(response, 'Date of Event (Optional)')
        self.assertLessEqual(len(queries), 1)

        with CaptureQueriesContext(connection) as warm_queries:
            warm_response = self.client.get(reverse('send-information'))
        self.assertEqual(warm_response.status_code, 200)
        self.assertEqual(len(warm_queries), 0)

    def test_submission_form_still_creates_pending_victim(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(reverse('send-information'), {
                'sender_fullname': 'Test Sender',
                'sender_address': 'Test Address',
                'sender_email': 'sender@example.com',
                'sender_phone': '+251900000000',
                'first_name': 'Test',
                'middle_name': 'Civilian',
                'last_name': 'Victim',
                'gender': 'Male',
                'age': '35',
                'perpetrator': 'Killed by Ethiopian forces',
                'woreda': self.woreda.woreda_name,
                'place': 'Test Place',
                'date_of_event': '2021-01-01',
                'remark': 'Test submission',
            })

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True})
        self.assertLessEqual(len(queries), 2)
        victim = Civilian_victims.objects.get(full_name='Test Civilian Victim')
        self.assertFalse(victim.approval)


class PhotoArchivePerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        woreda = Tigray_woreda.objects.create(
            woreda_name='Archive Test Woreda',
            latitude='13.5',
            longitude='39.5',
            zone='Test Zone',
        )
        Photo_archive.objects.bulk_create([
            Photo_archive(
                location=f'Archive Location {index:02d}',
                woreda=woreda,
                description=f'Archive description {index:02d}',
                photo=f'photo_archive/test-{index:02d}.jpg',
            )
            for index in range(14)
        ])

    def test_initial_archive_loads_six_records_with_bounded_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('archive-photo'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 6)
        self.assertEqual(response.context['filtered_count'], 14)
        self.assertContains(response, 'Load More')
        self.assertContains(response, 'htmx.min.js')
        self.assertLessEqual(len(queries), 3)

    def test_htmx_load_more_returns_batch_fragment_in_two_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse('archive-photo'),
                {'page': 2, 'append': 1},
                HTTP_HX_REQUEST='true',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public_partials/photo_archive_batch.html')
        self.assertEqual(len(response.context['page'].object_list), 6)
        self.assertContains(response, 'photo-archive-load-more')
        self.assertContains(response, 'page=3')
        self.assertNotContains(response, '<main')
        self.assertLessEqual(len(queries), 2)

    def test_htmx_filter_returns_only_the_archive_results_fragment(self):
        response = self.client.get(
            reverse('archive-photo'),
            {'woreda': 'Archive Test Woreda'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public_partials/photo_archive_results.html')
        self.assertContains(response, 'class="photo-archive-fragment"')
        self.assertNotContains(response, '<main')
        self.assertNotContains(response, 'class="breadcrumbs"')

    def test_boosted_navigation_returns_the_photo_archive_page_shell(self):
        response = self.client.get(
            reverse('archive-photo'),
            HTTP_HX_REQUEST='true',
            HTTP_HX_BOOSTED='true',
        )

        self.assertTemplateUsed(response, 'archive_by_photo.html')
        self.assertContains(response, 'id="page-content"')
        self.assertContains(response, 'Loading photo archives...')
