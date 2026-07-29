from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0098_webinar_date_created_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="photo_archive",
            index=models.Index(
                fields=["date_created"],
                name="photo_archive_created_idx",
            ),
        ),
    ]
