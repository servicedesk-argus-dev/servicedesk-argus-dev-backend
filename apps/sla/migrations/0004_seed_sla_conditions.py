from django.db import migrations

def seed_sla_conditions(apps, schema_editor):
    SLADefinition = apps.get_model('sla', 'SLADefinition')
    
    priorities = ["P1", "P2", "P3", "P4"]
    
    for priority in priorities:
        start_condition = {
            "condition": "AND",
            "rules": [
                {"field": "state", "operator": "in", "value": ["NEW", "IN_PROGRESS", "ESCALATED"]},
                {"field": "priority", "operator": "eq", "value": priority}
            ]
        }
        pause_condition = {
            "condition": "AND",
            "rules": [
                {"field": "state", "operator": "eq", "value": "ON_HOLD"}
            ]
        }
        stop_condition = {
            "condition": "AND",
            "rules": [
                {"field": "state", "operator": "in", "value": ["RESOLVED", "CLOSED", "CANCELLED"]}
            ]
        }
        
        SLADefinition.objects.filter(priority=priority).update(
            start_condition=start_condition,
            pause_condition=pause_condition,
            stop_condition=stop_condition
        )

class Migration(migrations.Migration):

    dependencies = [
        ('sla', '0003_alter_sladefinition_pause_condition_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_sla_conditions),
    ]
