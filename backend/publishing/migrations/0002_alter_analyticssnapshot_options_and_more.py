from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("publishing", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="analyticssnapshot",
            options={"ordering": ("-captured_at",)},
        ),
        migrations.AlterModelOptions(
            name="publicationjob",
            options={"ordering": ("-created_at",)},
        ),
    )
