from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teams", "0005_remove_noc_team"),
    ]

    operations = [
        migrations.AddField(
            model_name="teammember",
            name="is_assignable",
            field=models.BooleanField(
                default=True,
                help_text="When enabled this user can be selected as an assignee for records in this team.",
            ),
        ),
    ]
