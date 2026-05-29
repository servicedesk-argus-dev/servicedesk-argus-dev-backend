from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service_catalog", "0002_servicenow_request_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="catalog_item_label",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="category_label",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="estimated_delivery",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
