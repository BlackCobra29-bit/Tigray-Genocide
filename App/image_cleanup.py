"""Transaction-safe cleanup for files managed by WebPImageField."""

from functools import partial
from pathlib import PurePosixPath

from django.db import transaction

from .fields import WebPImageField


def webp_image_fields(model):
    return tuple(
        field for field in model._meta.concrete_fields
        if isinstance(field, WebPImageField)
    )


def remember_replaced_images(sender, instance, update_fields=None):
    """Remember old filenames before an update without deleting prematurely."""
    fields = webp_image_fields(sender)
    if update_fields is not None:
        fields = tuple(
            field for field in fields
            if field.name in update_fields or field.attname in update_fields
        )
    if instance._state.adding or not fields:
        return

    try:
        previous = sender._default_manager.only(
            *(field.attname for field in fields)
        ).get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    replaced = []
    for field in fields:
        old_image = getattr(previous, field.attname)
        new_image = getattr(instance, field.attname)
        old_name = old_image.name
        new_name = new_image.name
        if old_name and (old_name != new_name or not new_image._committed):
            replaced.append((field.name, old_name))

    instance._replaced_webp_images = replaced


def _delete_optimized_derivatives(storage, source_name):
    source = PurePosixPath(source_name)
    optimized_directory = str(source.parent / "optimized")
    try:
        _, filenames = storage.listdir(optimized_directory)
    except (AttributeError, FileNotFoundError, NotImplementedError, OSError):
        return

    prefix = f"{source.stem}."
    for filename in filenames:
        if filename.startswith(prefix) and filename.endswith(".webp"):
            storage.delete(str(PurePosixPath(optimized_directory) / filename))


def _delete_if_unreferenced(model, field_name, filename):
    field = model._meta.get_field(field_name)
    default_name = field.get_default() if field.has_default() else None
    if not filename or filename == default_name:
        return

    if model._default_manager.filter(**{field_name: filename}).exists():
        return

    _delete_optimized_derivatives(field.storage, filename)
    field.storage.delete(filename)


def schedule_replaced_image_cleanup(sender, instance):
    replaced = getattr(instance, "_replaced_webp_images", ())
    if hasattr(instance, "_replaced_webp_images"):
        del instance._replaced_webp_images

    for field_name, filename in replaced:
        transaction.on_commit(
            partial(_delete_if_unreferenced, sender, field_name, filename),
            robust=True,
        )


def remember_deleted_images(sender, instance):
    """Capture filenames before deferred model fields become unavailable."""
    fields = webp_image_fields(sender)
    if not fields or instance.pk is None:
        return

    filenames = sender._default_manager.filter(pk=instance.pk).values_list(
        *(field.attname for field in fields)
    ).first()
    if filenames is None:
        return

    instance._deleted_webp_images = [
        (field.name, filename)
        for field, filename in zip(fields, filenames)
        if filename
    ]


def schedule_deleted_image_cleanup(sender, instance):
    deleted = getattr(instance, "_deleted_webp_images", ())
    if hasattr(instance, "_deleted_webp_images"):
        del instance._deleted_webp_images

    for field_name, filename in deleted:
        transaction.on_commit(
            partial(_delete_if_unreferenced, sender, field_name, filename),
            robust=True,
        )
