from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0099_photo_archive_date_created_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="video_archive",
            index=models.Index(
                fields=["date_created"],
                name="video_archive_created_idx",
            ),
        ),
    ]
