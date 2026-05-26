from django.db import migrations


CANONICAL_TEAMS = {
    "NOC": "Global NOC queue",
    "Infra Team": "Infrastructure, network, hardware, and security resolver group",
    "DevOps Team": "DevOps, cloud, CI/CD, and platform resolver group",
    "Software Team": "Software, application, database, and configuration resolver group",
}

LEGACY_TEAM_ALIASES = {
    "Database Operations": "Software Team",
    "Network Operations": "Infra Team",
    "Platform Operations": "DevOps Team",
    "Service Desk": "NOC",
    "Facilities": "NOC",
}


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


def _ensure_global_teams(models):
    Team = models["Team"]
    canonical = {}
    for name, description in CANONICAL_TEAMS.items():
        team, created = Team.objects.get_or_create(
            name=name,
            organization=None,
            defaults={
                "description": description,
                "is_active": True,
            },
        )
        updates = []
        if not team.is_active:
            team.is_active = True
            updates.append("is_active")
        if not team.description or "resolver group for" in str(team.description).lower():
            team.description = description
            updates.append("description")
        if updates:
            team.save(update_fields=updates)
        canonical[name] = team
    return canonical


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
        model = models[model_name]
        model.objects.filter(**{field_name: old_team}).update(**{field_name: new_team})

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


def consolidate_seeded_teams(apps, schema_editor):
    models = _models(apps)
    Team = models["Team"]
    canonical = _ensure_global_teams(models)

    for team_name, target_name in {**{name: name for name in CANONICAL_TEAMS}, **LEGACY_TEAM_ALIASES}.items():
        target = canonical[target_name]
        for team in list(Team.objects.filter(name=team_name).exclude(id=target.id)):
            _merge_team(team, target, models)


class Migration(migrations.Migration):
    dependencies = [
        ("teams", "0003_team_optional_organization"),
        ("assignments", "0001_initial"),
        ("incidents", "0014_incident_source_alert_state_idx"),
        ("changes", "0003_maintenancewindow_riskassessment"),
        ("problems", "0002_problemtask"),
        ("assets", "0005_configurationitem_firewall_type_and_more"),
        ("learning", "0001_initial"),
        ("service_catalog", "0002_servicenow_request_fields"),
    ]

    operations = [
        migrations.RunPython(consolidate_seeded_teams, migrations.RunPython.noop),
    ]
