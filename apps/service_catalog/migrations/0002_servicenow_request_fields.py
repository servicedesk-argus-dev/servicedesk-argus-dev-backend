import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def normalize_states(apps, _schema_editor):
    ServiceRequest = apps.get_model("service_catalog", "ServiceRequest")
    RequestedItem = apps.get_model("service_catalog", "RequestedItem")

    ServiceRequest.objects.filter(state="DRAFT").update(state="NEW")
    ServiceRequest.objects.filter(state="PENDING_APPROVAL").update(state="APPROVAL")

    RequestedItem.objects.filter(state="PENDING_APPROVAL").update(state="PENDING")
    RequestedItem.objects.filter(state="FULFILLMENT").update(state="IN_PROGRESS")
    RequestedItem.objects.filter(state="COMPLETED").update(state="FULFILLED")


def backfill_updated_at(apps, _schema_editor):
    now = django.utils.timezone.now()
    CatalogCategory = apps.get_model("service_catalog", "CatalogCategory")
    CatalogItem = apps.get_model("service_catalog", "CatalogItem")
    CatalogCategory.objects.filter(updated_at__isnull=True).update(updated_at=now)
    CatalogItem.objects.filter(updated_at__isnull=True).update(updated_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0003_service_catalog_sequences"),
        ("service_catalog", "0001_initial"),
        ("teams", "0003_team_optional_organization"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="catalogcategory",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="catalogcategory",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="catalogcategory",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="approval_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="currency",
            field=models.CharField(default="USD", max_length=3),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="estimated_days",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="form_schema",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="fulfillment_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="catalog_items",
                to="teams.team",
            ),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="type",
            field=models.CharField(
                choices=[
                    ("HARDWARE", "Hardware"),
                    ("SOFTWARE", "Software"),
                    ("ACCESS", "Access"),
                    ("GENERAL", "General"),
                    ("SERVICE", "Service"),
                ],
                default="GENERAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="catalogitem",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(backfill_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="catalogcategory",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="catalogitem",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="requesteditem",
            name="notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_service_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_service_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="assignment_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="service_requests",
                to="teams.team",
            ),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="cancel_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="fulfilled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="priority",
            field=models.CharField(default="P3", max_length=2),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="short_description",
            field=models.CharField(default="", max_length=255),
        ),
        migrations.RunPython(normalize_states, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="requesteditem",
            name="state",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("IN_PROGRESS", "Work in Progress"),
                    ("FULFILLED", "Fulfilled"),
                    ("CLOSED", "Closed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="servicerequest",
            name="state",
            field=models.CharField(
                choices=[
                    ("NEW", "New"),
                    ("APPROVAL", "Approval"),
                    ("APPROVED", "Approved"),
                    ("FULFILLMENT", "Work in Progress"),
                    ("FULFILLED", "Fulfilled"),
                    ("CLOSED", "Closed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="NEW",
                max_length=20,
            ),
        ),
    ]
