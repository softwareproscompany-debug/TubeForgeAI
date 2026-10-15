from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("channels", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="automationrule",
            options={"ordering": ("name",)},
        ),
        migrations.AlterModelOptions(
            name="channel",
            options={"ordering": ("-created_at",)},
        ),
    )
