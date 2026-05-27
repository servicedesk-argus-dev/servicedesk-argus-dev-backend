import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization
from apps.teams.models import Team

User = get_user_model()


class AssignmentRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    conditions = models.JSONField(help_text="JSON conditions for rule matching")
    target_group = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='assignment_rules')
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignment_rules')
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='assignment_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assignment_rules"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class CategoryGroupMapping(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='category_mappings')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='category_mappings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "category_group_mappings"
        unique_together = ["organization", "category", "subcategory"]

    def __str__(self):
        return f"{self.category} -> {self.team.name}"


class UserSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    skill_name = models.CharField(max_length=100)
    proficiency = models.PositiveSmallIntegerField(default=1, help_text="Proficiency level 1-5")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_skills')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_skills"
        unique_together = ["user", "skill_name"]

    def __str__(self):
        return f"{self.user.email}: {self.skill_name} ({self.proficiency})"


class SkillRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    skill_name = models.CharField(max_length=100)
    min_proficiency = models.PositiveSmallIntegerField(default=1)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='skill_requirements')

    class Meta:
        db_table = "skill_requirements"
        unique_together = ["organization", "category", "subcategory", "skill_name"]

    def __str__(self):
        return f"{self.category}: Requires {self.skill_name}"


class RoundRobinCounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='round_robin_counter')
    last_assigned_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    last_assigned_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='round_robin_counters')

    class Meta:
        db_table = "round_robin_counters"
        unique_together = ["organization", "team"]

    def __str__(self):
        return f"Round Robin for {self.team.name}"
