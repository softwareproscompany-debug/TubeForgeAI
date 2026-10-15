from django.db import migrations


class Migration(migrations.Migration):
    dependencies = (("core", "0002_alter_systemsetting_options"),)

    operations = (
        migrations.AlterModelOptions(
            name="auditevent",
            options={"ordering": ("-occurred_at",)},
        ),
        migrations.AlterModelOptions(
            name="notification",
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterModelOptions(
            name="user",
            options={},
        ),
    )
