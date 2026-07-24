from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0094_analysis_articles_app_analysi_approva_40c0ba_idx_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="civilian_victims",
            index=models.Index(fields=["approval", "zone"], name="App_civilia_approva_7ef319_idx"),
        ),
        migrations.AddIndex(
            model_name="unverified_civilian",
            index=models.Index(fields=["zone", "date_created"], name="App_unverif_zone_3dfb90_idx"),
        ),
    ]
