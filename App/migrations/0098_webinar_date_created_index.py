from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0097_civilian_victim_duplicate_lookup_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="webinar",
            index=models.Index(
                fields=["date_created"],
                name="webinar_created_idx",
            ),
        ),
    ]
