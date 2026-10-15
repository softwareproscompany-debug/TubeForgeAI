from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("projects", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="asset",
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterModelOptions(
            name="project",
            options={"ordering": ("-updated_at",)},
        ),
        migrations.AlterModelOptions(
            name="renderjob",
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterModelOptions(
            name="scene",
            options={"ordering": ("position",)},
        ),
        migrations.AlterModelOptions(
            name="scriptversion",
            options={"ordering": ("-version_number",)},
        ),
        migrations.AlterModelOptions(
            name="timelineversion",
            options={"ordering": ("-version_number",)},
        ),
    )
