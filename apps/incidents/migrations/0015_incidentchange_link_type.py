from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0014_incident_source_alert_state_idx"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE incident_changes "
                        "ADD COLUMN IF NOT EXISTS link_type varchar(30) "
                        "DEFAULT 'RELATED_CHANGE';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE incident_changes "
                        "DROP COLUMN IF EXISTS link_type;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "UPDATE incident_changes "
                        "SET link_type = 'RELATED_CHANGE' "
                        "WHERE link_type IS NULL OR link_type = '';"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE incident_changes "
                        "ALTER COLUMN link_type SET NOT NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE incident_changes "
                        "ALTER COLUMN link_type DROP NOT NULL;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="incidentchange",
                    name="link_type",
                    field=models.CharField(
                        choices=[
                            ("RELATED_CHANGE", "Related Change"),
                            ("FIXED_BY_CHANGE", "Fixed By Change"),
                            ("CAUSED_BY_CHANGE", "Caused By Change"),
                        ],
                        default="RELATED_CHANGE",
                        max_length=30,
                    ),
                ),
            ],
        ),
    ]
