from django.db import migrations


ROLE_TOKEN_TO_NAME = {
    "SUPER_ADMIN": "Super Admin",
    "ORG_ADMIN": "Org Admin",
    "MANAGER": "Manager",
    "ENGINEER": "Engineer",
    "TEAM_LEAD": "Team Lead",
    "NOC": "NOC",
    "CLIENT_USER": "Client User",
    "OPERATOR": "Operator",
    "VIEWER": "Viewer",
}


def role_token_name(role_name):
    return str(role_name or "").strip().upper().replace("-", "_").replace(" ", "_")


def canonical_role_name(role_name):
    raw = str(role_name or "").strip()
    return ROLE_TOKEN_TO_NAME.get(role_token_name(raw), raw)


def normalize_roles(apps, _schema_editor):
    Role = apps.get_model("accounts", "Role")
    UserInvitation = apps.get_model("accounts", "UserInvitation")

    for role in list(Role.objects.all()):
        canonical_name = canonical_role_name(role.name)
        if not canonical_name or canonical_name == role.name:
            continue

        canonical_role, _ = Role.objects.get_or_create(
            name=canonical_name,
            defaults={
                "description": role.description,
                "is_system": role.is_system,
            },
        )
        if role.permissions.exists():
            canonical_role.permissions.add(*role.permissions.all())

        for user in role.users.all():
            user.roles.add(canonical_role)
            user.roles.remove(role)

        for invitation in UserInvitation.objects.filter(roles=role):
            invitation.roles.add(canonical_role)
            invitation.roles.remove(role)

        if not role.users.exists() and not UserInvitation.objects.filter(roles=role).exists():
            role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_user_keycloak_cache_fields"),
    ]

    operations = [
        migrations.RunPython(normalize_roles, migrations.RunPython.noop),
    ]
