from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("providers", "0002_alter_budget_options"),)

    operations = (
        migrations.AlterModelOptions(
            name="aimodel",
            options={"ordering": ("model_identifier",)},
        ),
        migrations.AlterModelOptions(
            name="generationjob",
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterModelOptions(
            name="provider",
            options={"ordering": ("-priority", "name")},
        ),
        migrations.AlterModelOptions(
            name="resourceusageevent",
            options={"ordering": ("-occurred_at",)},
        ),
    )
