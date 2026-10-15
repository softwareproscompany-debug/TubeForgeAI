from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("workflows", "0001_initial"),)

    operations = (
        migrations.AlterModelOptions(
            name="approval",
            options={"ordering": ("-requested_at",)},
        ),
        migrations.AlterModelOptions(
            name="workflowevent",
            options={"ordering": ("occurred_at",)},
        ),
        migrations.AlterModelOptions(
            name="workflowrun",
            options={"ordering": ("-created_at",)},
        ),
    )
