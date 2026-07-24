from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0096_rename_app_civilia_approva_7ef319_idx_app_civilia_approva_9eefa3_idx_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="civilian_victims",
            index=models.Index(
                fields=["full_name", "woreda"],
                name="civilian_name_woreda_idx",
            ),
        ),
    ]
