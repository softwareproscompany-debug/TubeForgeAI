from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("providers", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="budget",
            options={"ordering": ("-created_at",)},
        ),
    )
