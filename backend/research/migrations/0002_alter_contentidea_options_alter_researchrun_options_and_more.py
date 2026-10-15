from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("research", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="contentidea",
            options={"ordering": ("-priority", "-created_at")},
        ),
        migrations.AlterModelOptions(
            name="researchrun",
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterModelOptions(
            name="researchsource",
            options={"ordering": ("title",)},
        ),
    )
