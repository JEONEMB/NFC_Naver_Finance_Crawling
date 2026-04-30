from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DiscussionPipelineResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "requirement_number",
                    models.CharField(default="F102", max_length=20),
                ),
                ("requested_company_name", models.CharField(max_length=100)),
                ("actual_stock_name", models.CharField(max_length=100)),
                ("stock_code", models.CharField(blank=True, max_length=6)),
                ("original_comments", models.JSONField(default=list)),
                ("cleaned_comments", models.JSONField(default=list)),
                ("augmented_comments", models.JSONField(default=list)),
                ("iqr_thresholds", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
