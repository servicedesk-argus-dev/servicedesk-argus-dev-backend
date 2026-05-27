from django.db import migrations


INFRA_TEAM_NAME = "Infra Team"


def _models(apps):
    return {
        "Team": apps.get_model("teams", "Team"),
        "TeamMember": apps.get_model("teams", "TeamMember"),
        "EscalationPolicy": apps.get_model("teams", "EscalationPolicy"),
        "AssignmentRule": apps.get_model("assignments", "AssignmentRule"),
        "CategoryGroupMapping": apps.get_model("assignments", "CategoryGroupMapping"),
        "RoundRobinCounter": apps.get_model("assignments", "RoundRobinCounter"),
        "Incident": apps.get_model("incidents", "Incident"),
        "Change": apps.get_model("changes", "Change"),
        "MaintenanceWindow": apps.get_model("changes", "MaintenanceWindow"),
        "Problem": apps.get_model("problems", "Problem"),
        "ProblemTask": apps.get_model("problems", "ProblemTask"),
        "ConfigurationItem": apps.get_model("assets", "ConfigurationItem"),
        "LearningTrack": apps.get_model("learning", "LearningTrack"),
        "CatalogItem": apps.get_model("service_catalog", "CatalogItem"),
        "ServiceRequest": apps.get_model("service_catalog", "ServiceRequest"),
        "CatalogTask": apps.get_model("service_catalog", "CatalogTask"),
    }


def _move_m2m_memberships(old_team, new_team, models):
    MaintenanceWindow = models["MaintenanceWindow"]
    through = MaintenanceWindow.affected_groups.through
    for row in through.objects.filter(team_id=old_team.id):
        through.objects.get_or_create(
            maintenancewindow_id=row.maintenancewindow_id,
            team_id=new_team.id,
        )
    through.objects.filter(team_id=old_team.id).delete()


def _merge_team(old_team, new_team, models):
    if old_team.id == new_team.id:
        return

    TeamMember = models["TeamMember"]
    for member in TeamMember.objects.filter(team=old_team):
        TeamMember.objects.get_or_create(
            team=new_team,
            user_id=member.user_id,
            defaults={"role": member.role},
        )

    fk_updates = (
        ("Incident", "assignment_group"),
        ("Change", "assignment_group"),
        ("Problem", "assignment_group"),
        ("ProblemTask", "assignment_group"),
        ("ConfigurationItem", "support_group"),
        ("LearningTrack", "team"),
        ("CatalogItem", "fulfillment_group"),
        ("ServiceRequest", "assignment_group"),
        ("CatalogTask", "assignment_group"),
        ("EscalationPolicy", "team"),
        ("AssignmentRule", "target_group"),
        ("CategoryGroupMapping", "team"),
    )
    for model_name, field_name in fk_updates:
        models[model_name].objects.filter(**{field_name: old_team}).update(**{field_name: new_team})

    RoundRobinCounter = models["RoundRobinCounter"]
    for counter in RoundRobinCounter.objects.filter(team=old_team):
        duplicate = RoundRobinCounter.objects.filter(
            organization_id=counter.organization_id,
            team=new_team,
        ).exclude(id=counter.id).first()
        if duplicate:
            counter.delete()
        else:
            counter.team = new_team
            counter.save(update_fields=["team"])

    _move_m2m_memberships(old_team, new_team, models)
    old_team.delete()


def remove_noc_team(apps, schema_editor):
    models = _models(apps)
    Team = models["Team"]
    infra_team, _created = Team.objects.get_or_create(
        name=INFRA_TEAM_NAME,
        organization=None,
        defaults={
            "description": "Infrastructure, network, hardware, and security resolver group",
            "is_active": True,
        },
    )

    for noc_team in list(Team.objects.filter(name__iexact="NOC")):
        _merge_team(noc_team, infra_team, models)


class Migration(migrations.Migration):
    dependencies = [
        ("teams", "0004_consolidate_seeded_teams"),
    ]

    operations = [
        migrations.RunPython(remove_noc_team, migrations.RunPython.noop),
    ]
