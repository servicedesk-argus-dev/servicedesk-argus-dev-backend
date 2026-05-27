from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.realtime import emit_record_event

from .models import LearningEnrollment, LearningProgress, LearningTrack


def _emit_learning(instance, action="updated"):
    transaction.on_commit(lambda: emit_record_event("learning", instance, action))


@receiver(post_save, sender=LearningTrack)
def learning_track_realtime_event(sender, instance, created, **kwargs):
    _emit_learning(instance, "created" if created else "updated")


@receiver(post_save, sender=LearningEnrollment)
def learning_enrollment_realtime_event(sender, instance, created, **kwargs):
    _emit_learning(instance, "created" if created else "updated")


@receiver(post_save, sender=LearningProgress)
def learning_progress_realtime_event(sender, instance, created, **kwargs):
    _emit_learning(instance.enrollment, "updated")

