from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django_summernote.utils import get_attachment_model
from PIL import Image

from .models import (
    Administrator,
    Analysis_articles,
    Civilian_victims,
    Hero_images,
    Photo_archive,
)


def image_upload(name="upload.png", *, mode="RGB", size=(40, 24), color=None):
    if color is None:
        color = (30, 100, 180, 120) if "A" in mode else (30, 100, 180)
    image = Image.new(mode, size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def oriented_jpeg_upload():
    image = Image.new("RGB", (40, 20), (170, 60, 20))
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise when displayed.
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return SimpleUploadedFile(
        "phone-photo.jpg", output.getvalue(), content_type="image/jpeg"
    )


class WebPImageUploadTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            MEDIA_URL="/media/",
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.media_directory.cleanup()

    def assert_stored_as_webp(self, image_field, expected_directory):
        self.assertTrue(image_field.name.startswith(f"{expected_directory}/"))
        self.assertTrue(image_field.name.endswith(".webp"))
        with image_field.storage.open(image_field.name, "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.format, "WEBP")

    def test_all_image_models_convert_new_uploads_to_webp(self):
        user = User.objects.create_user(username="image-admin")
        records = (
            (
                Civilian_victims.objects.create(
                    full_name="Test Victim",
                    gender="Unknown",
                    zone="Test Zone",
                    perpetrator="Killed by Ethiopian forces",
                    picture=image_upload("victim.PNG"),
                ).picture,
                "civilian_victims_pic",
            ),
            (
                Analysis_articles.objects.create(
                    author=user,
                    title="Test article",
                    content="Article content",
                    thumbnail=image_upload("article.jpeg"),
                ).thumbnail,
                "articles_thumbnail",
            ),
            (
                Photo_archive.objects.create(
                    author=user,
                    location="Test location",
                    description="Archive description",
                    photo=image_upload("archive.tiff"),
                ).photo,
                "photo_archive",
            ),
            (
                Administrator.objects.create(
                    user=user,
                    admin_photo=image_upload("profile.bmp"),
                ).admin_photo,
                "admin_pic",
            ),
            (
                Hero_images.objects.create(
                    hero_image=image_upload("homepage.jpg")
                ).hero_image,
                "hero-images",
            ),
        )

        for image_field, expected_directory in records:
            with self.subTest(field=image_field.name):
                self.assert_stored_as_webp(image_field, expected_directory)

    def test_transparency_is_preserved(self):
        hero = Hero_images.objects.create(
            hero_image=image_upload(mode="RGBA", color=(20, 40, 60, 0))
        )

        with hero.hero_image.storage.open(hero.hero_image.name, "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_summernote_editor_image_is_also_converted(self):
        attachment_model = get_attachment_model()
        attachment = attachment_model.objects.create(
            file=image_upload("article-body.png")
        )

        self.assertTrue(attachment.file.name.endswith(".webp"))
        self.assertTrue(attachment.name.endswith(".webp"))
        with attachment.file.storage.open(attachment.file.name, "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.format, "WEBP")

    def test_exif_orientation_is_applied_and_metadata_is_removed(self):
        hero = Hero_images.objects.create(hero_image=oriented_jpeg_upload())

        with hero.hero_image.storage.open(hero.hero_image.name, "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.size, (20, 40))
                self.assertFalse(image.getexif())

    def test_existing_default_filename_is_not_converted(self):
        victim = Civilian_victims.objects.create(
            full_name="Default Picture",
            gender="Male",
            zone="Test Zone",
            perpetrator="Killed by Ethiopian forces",
        )

        self.assertEqual(victim.picture.name, "civilian_victims_pic/default.png")

    def test_replacing_and_deleting_uploads_removes_unreferenced_files(self):
        hero = Hero_images.objects.create(hero_image=image_upload("first.png"))
        storage = hero.hero_image.storage
        first_name = hero.hero_image.name

        with self.captureOnCommitCallbacks(execute=True):
            hero.hero_image = image_upload("second.jpg")
            hero.save(update_fields=["hero_image"])

        second_name = hero.hero_image.name
        self.assertNotEqual(first_name, second_name)
        self.assertFalse(storage.exists(first_name))
        self.assertTrue(storage.exists(second_name))

        with self.captureOnCommitCallbacks(execute=True):
            hero.delete()

        self.assertFalse(storage.exists(second_name))

    def test_image_is_not_replaced_when_excluded_from_update_fields(self):
        hero = Hero_images.objects.create(hero_image=image_upload("first.png"))
        storage = hero.hero_image.storage
        first_name = hero.hero_image.name

        with self.captureOnCommitCallbacks(execute=True):
            hero.hero_image = image_upload("ignored.jpg")
            hero.date_created = hero.date_created
            hero.save(update_fields=["date_created"])

        hero.refresh_from_db()
        self.assertEqual(hero.hero_image.name, first_name)
        self.assertTrue(storage.exists(first_name))

    def test_shared_default_image_is_never_deleted(self):
        default_name = "civilian_victims_pic/default.png"
        field = Civilian_victims._meta.get_field("picture")
        field.storage.save(default_name, ContentFile(b"shared default"))
        victim = Civilian_victims.objects.create(
            full_name="Protected Default",
            gender="Male",
            zone="Test Zone",
            perpetrator="Killed by Ethiopian forces",
        )

        with self.captureOnCommitCallbacks(execute=True):
            victim.delete()

        self.assertTrue(field.storage.exists(default_name))
        Path(field.storage.path(default_name)).unlink()
