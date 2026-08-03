import uuid

from django.db import models

from .image_uploads import replace_field_file_with_webp


class Char32UUIDField(models.UUIDField):
    """Store UUID values in the project's existing CHAR(32) columns."""

    def db_type(self, connection):
        return "char(32)"

    def get_db_prep_value(self, value, connection, prepared=False):
        if value is None:
            return None

        if not isinstance(value, uuid.UUID):
            value = self.to_python(value)

        return value.hex


class WebPImageField(models.ImageField):
    """An ImageField that converts only new uploads to WebP before storage."""

    def __init__(self, *args, webp_quality=82, webp_method=6, **kwargs):
        self.webp_quality = webp_quality
        self.webp_method = webp_method
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.webp_quality != 82:
            kwargs["webp_quality"] = self.webp_quality
        if self.webp_method != 6:
            kwargs["webp_method"] = self.webp_method
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        image = getattr(model_instance, self.attname)
        if image and not image._committed:
            replace_field_file_with_webp(
                image,
                quality=self.webp_quality,
                method=self.webp_method,
            )

        return super().pre_save(model_instance, add)
