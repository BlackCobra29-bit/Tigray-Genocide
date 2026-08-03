"""Utilities for normalizing newly uploaded images to WebP."""

from io import BytesIO
from pathlib import PurePosixPath

from django.core.checks import Error, register
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError, features


@register()
def check_webp_encoder_support(app_configs, **kwargs):
    """Fail deployment checks early if Pillow cannot encode WebP images."""
    if features.check("webp"):
        return []
    return [
        Error(
            "Pillow was installed without WebP encoder support.",
            hint="Install a Pillow build with libwebp support before accepting uploads.",
            id="App.E001",
        )
    ]


def _webp_frame(image):
    """Return a WebP-compatible frame while preserving transparency."""
    has_transparency = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
    return image.convert("RGBA" if has_transparency else "RGB")


def _webp_filename(filename):
    """Keep the uploaded basename and replace only its extension."""
    normalized_name = str(filename).replace("\\", "/")
    path = PurePosixPath(normalized_name)
    return str(path.with_suffix(".webp"))


def convert_uploaded_image_to_webp(uploaded_file, *, quality=82, method=6):
    """Convert an uploaded image to an in-memory, metadata-free WebP file.

    The original pixel dimensions are retained. EXIF orientation is applied
    before metadata is discarded, and alpha transparency is preserved.
    Animated images retain their frames and timing.
    """
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            output = BytesIO()

            if getattr(source, "is_animated", False):
                durations = []
                frames = []
                for frame in ImageSequence.Iterator(source):
                    durations.append(frame.info.get("duration", source.info.get("duration", 0)))
                    normalized = ImageOps.exif_transpose(frame.copy())
                    frames.append(_webp_frame(normalized))

                frames[0].save(
                    output,
                    format="WEBP",
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=source.info.get("loop", 0),
                    quality=quality,
                    method=method,
                    exact=True,
                )
            else:
                source.load()
                normalized = ImageOps.exif_transpose(source)
                _webp_frame(normalized).save(
                    output,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    exact=True,
                )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(
            "The uploaded image could not be converted to WebP. "
            "Please upload a valid image file."
        ) from exc

    output.seek(0)
    return ContentFile(output.read(), name=_webp_filename(uploaded_file.name))


def replace_field_file_with_webp(field_file, *, quality=82, method=6):
    """Replace a new FieldFile's in-memory content with its WebP version."""
    converted = convert_uploaded_image_to_webp(
        field_file.file,
        quality=quality,
        method=method,
    )
    field_file.file = converted
    field_file.name = converted.name
    field_file._committed = False
    return field_file
