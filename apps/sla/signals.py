from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.incidents.models import Incident
from apps.problems.models import Problem
from apps.changes.models import Change
from apps.sla.engine import process_task_slas

@receiver(post_save, sender=Incident)
@receiver(post_save, sender=Problem)
@receiver(post_save, sender=Change)
def trigger_sla_evaluation(sender, instance, created, **kwargs):
    """
    Triggers the SLA Engine whenever a task (Incident, Problem, or Change) is created or updated.
    """
    process_task_slas(instance)
