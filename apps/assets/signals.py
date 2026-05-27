import json
import uuid
from datetime import date, datetime

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notifications.realtime import emit_record_event

from .models import ConfigurationItem, ConfigurationItemHistory


def _serialize_history_value(value):
    if value is None:
        return ""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


@receiver(pre_save, sender=ConfigurationItem)
def configuration_item_pre_save_snapshot(sender, instance, **kwargs):
    if not instance.pk:
        instance._pre_save_state = None
        return
    instance._pre_save_state = ConfigurationItem.all_objects.filter(pk=instance.pk).values().first()


@receiver(post_save, sender=ConfigurationItem)
def configuration_item_history_logger(sender, instance, created, **kwargs):
    changed_by = getattr(instance, "_changed_by", None)
    change_source = getattr(instance, "_change_source", ConfigurationItemHistory.ChangeSource.SYSTEM)
    transaction.on_commit(lambda: emit_record_event("asset", instance, "created" if created else "updated"))

    if created:
        ConfigurationItemHistory.objects.create(
            configuration_item=instance,
            organization=instance.organization,
            changed_by=changed_by,
            change_source=change_source,
            field_name="created",
            old_value="",
            new_value="created",
        )
        return

    previous = getattr(instance, "_pre_save_state", None) or {}
    if not previous:
        return

    excluded_fields = {"created_at", "updated_at"}

    for field in instance._meta.concrete_fields:
        if field.name in excluded_fields:
            continue

        old_value = previous.get(field.attname)
        new_value = getattr(instance, field.attname)

        if _serialize_history_value(old_value) == _serialize_history_value(new_value):
            continue

        ConfigurationItemHistory.objects.create(
            configuration_item=instance,
            organization=instance.organization,
            changed_by=changed_by,
            change_source=change_source,
            field_name=field.name,
            old_value=_serialize_history_value(old_value),
            new_value=_serialize_history_value(new_value),
        )
