from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("naver", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="discussionpipelineresult",
            name="integrated_data",
            field=models.JSONField(default=list),
        ),
    ]
