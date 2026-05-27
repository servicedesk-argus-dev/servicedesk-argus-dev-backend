from django.db import migrations, models


def ensure_keycloak_cache_columns(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    table_name = User._meta.db_table
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }

    fields = [
        models.CharField(max_length=255, blank=True, default="", db_index=True, name="keycloak_subject"),
        models.JSONField(default=list, blank=True, name="keycloak_roles"),
        models.JSONField(default=list, blank=True, name="keycloak_permissions"),
        models.DateTimeField(null=True, blank=True, name="keycloak_last_sync"),
    ]
    for field in fields:
        field.set_attributes_from_name(field.name)
        if field.name not in existing_columns:
            schema_editor.add_field(User, field)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_learning_permissions"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(ensure_keycloak_cache_columns, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="keycloak_subject",
                    field=models.CharField(blank=True, db_index=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="user",
                    name="keycloak_roles",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="user",
                    name="keycloak_permissions",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="user",
                    name="keycloak_last_sync",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
