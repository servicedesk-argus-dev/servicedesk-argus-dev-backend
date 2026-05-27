# Generated for global resolver teams in the client-account service desk.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teams", "0002_escalationpolicy_escalationstep"),
    ]

    operations = [
        migrations.AlterField(
            model_name="team",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                help_text="Blank for global FinSpot resolver teams such as NOC.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teams",
                to="organizations.organization",
            ),
        ),
    ]
