import hashlib
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def _original_url(image_field):
    try:
        return image_field.url if image_field else ""
    except (AttributeError, ValueError):
        return ""


def get_optimized_image_url(
    image_field,
    max_width,
    max_height=None,
    quality=82,
):
    """Return a cached WebP derivative while preserving the source aspect ratio."""
    original_url = _original_url(image_field)
    if not original_url:
        return ""

    try:
        max_width = int(max_width)
        max_height = int(max_height or max_width * 2)
        quality = int(quality)
        source_name = image_field.name
        storage = image_field.storage
        source_size = storage.size(source_name)

        try:
            modified = storage.get_modified_time(source_name).timestamp()
        except (AttributeError, NotImplementedError, OSError, ValueError):
            modified = ""

        fingerprint_source = (
            f"{source_name}:{source_size}:{modified}:"
            f"{max_width}:{max_height}:{quality}"
        )
        fingerprint = hashlib.blake2s(
            fingerprint_source.encode("utf-8"),
            digest_size=6,
        ).hexdigest()

        source_path = PurePosixPath(source_name)
        optimized_name = str(
            source_path.parent
            / "optimized"
            / f"{source_path.stem}.{fingerprint}.{max_width}w.webp"
        )

        if storage.exists(optimized_name):
            return storage.url(optimized_name)

        with storage.open(source_name, "rb") as source:
            image = Image.open(source)
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (max_width, max_height),
                Image.Resampling.LANCZOS,
            )

            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")

            output = BytesIO()
            image.save(
                output,
                format="WEBP",
                quality=quality,
                method=6,
            )

        saved_name = storage.save(
            optimized_name,
            ContentFile(output.getvalue()),
        )
        return storage.url(saved_name)
    except (
        AttributeError,
        FileNotFoundError,
        OSError,
        TypeError,
        UnidentifiedImageError,
        ValueError,
    ):
        return original_url
