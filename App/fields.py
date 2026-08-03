import uuid

from django.db import models


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
