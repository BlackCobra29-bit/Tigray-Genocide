# Generated manually to introduce storage-level WebP normalization.

import App.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0101_preserve_char32_uuid"),
    ]

    operations = [
        migrations.AlterField(
            model_name="administrator",
            name="admin_photo",
            field=App.fields.WebPImageField(
                default="admin_pic/default.png", upload_to="admin_pic"
            ),
        ),
        migrations.AlterField(
            model_name="analysis_articles",
            name="thumbnail",
            field=App.fields.WebPImageField(
                help_text="Upload a thumbnail image for this article.",
                upload_to="articles_thumbnail",
            ),
        ),
        migrations.AlterField(
            model_name="civilian_victims",
            name="picture",
            field=App.fields.WebPImageField(
                blank=True,
                default="civilian_victims_pic/default.png",
                upload_to="civilian_victims_pic",
            ),
        ),
        migrations.AlterField(
            model_name="hero_images",
            name="hero_image",
            field=App.fields.WebPImageField(upload_to="hero-images"),
        ),
        migrations.AlterField(
            model_name="photo_archive",
            name="photo",
            field=App.fields.WebPImageField(upload_to="photo_archive"),
        ),
    ]
