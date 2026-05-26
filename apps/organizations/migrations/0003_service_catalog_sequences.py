from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0002_organization_last_change_number_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="last_service_request_number",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="organization",
            name="last_requested_item_number",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="organization",
            name="last_catalog_task_number",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
