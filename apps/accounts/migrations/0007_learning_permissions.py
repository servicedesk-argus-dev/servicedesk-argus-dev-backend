from django.db import migrations


LEARNING_PERMISSIONS = {
    "learning:read": "View Learning Hub tracks, modules, and assigned KT.",
    "learning:complete": "Mark assigned Learning Hub modules complete or incomplete.",
    "learning:assign": "Assign Learning Hub tracks and review progress.",
    "learning:manage": "Create and update Learning Hub tracks and modules.",
}


def create_learning_permissions(apps, _schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, description in LEARNING_PERMISSIONS.items():
        Permission.objects.get_or_create(code=code, defaults={"description": description})


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_must_change_password"),
    ]

    operations = [
        migrations.RunPython(create_learning_permissions, migrations.RunPython.noop),
    ]
