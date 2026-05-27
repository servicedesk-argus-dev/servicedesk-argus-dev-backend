from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.incidents.models import Incident
from apps.problems.models import Problem
from apps.changes.models import Change
from .engine import process_automations
from .models import AutomationRule

@receiver(post_save, sender=Incident)
def trigger_incident_automation(sender, instance, created, **kwargs):
    event = AutomationRule.Trigger.ON_CREATE if created else AutomationRule.Trigger.ON_UPDATE
    process_automations(instance, event)

@receiver(post_save, sender=Problem)
def trigger_problem_automation(sender, instance, created, **kwargs):
    event = AutomationRule.Trigger.ON_CREATE if created else AutomationRule.Trigger.ON_UPDATE
    process_automations(instance, event)

@receiver(post_save, sender=Change)
def trigger_change_automation(sender, instance, created, **kwargs):
    event = AutomationRule.Trigger.ON_CREATE if created else AutomationRule.Trigger.ON_UPDATE
    process_automations(instance, event)
