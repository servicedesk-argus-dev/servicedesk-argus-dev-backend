from django.db import transaction, models
from django.utils import timezone

def get_next_sequence_number(organization, sequence_field):
    """
    Atomically increments and returns the next sequence number for an organization.
    sequence_field: 'last_incident_number', 'last_change_number', or 'last_problem_number'
    """
    with transaction.atomic():
        # Select for update to prevent race conditions
        org = organization.__class__.objects.select_for_update().get(pk=organization.pk)
        
        # Use F() expression to increment safely
        setattr(org, sequence_field, models.F(sequence_field) + 1)
        org.save(update_fields=[sequence_field])
        
        # Reload to get the new value
        org.refresh_from_db()
        return getattr(org, sequence_field)

def _model_for_record_prefix(prefix):
    if prefix == "INC":
        from apps.incidents.models import Incident

        return Incident
    if prefix == "CHG":
        from apps.changes.models import Change

        return Change
    if prefix == "PRB":
        from apps.problems.models import Problem

        return Problem
    if prefix == "REQ":
        from apps.service_catalog.models import ServiceRequest

        return ServiceRequest
    if prefix == "RITM":
        from apps.service_catalog.models import RequestedItem

        return RequestedItem
    if prefix == "SCTASK":
        from apps.service_catalog.models import CatalogTask

        return CatalogTask
    return None


def generate_record_number(prefix, organization, sequence_field):
    """
    Generates a record number like INC202610001
    """
    year = timezone.now().year
    model_cls = _model_for_record_prefix(prefix)
    for _ in range(1000):
        seq = get_next_sequence_number(organization, sequence_field)
        # Pads to 5 digits, e.g. 00001
        number = f"{prefix}{year}{seq:05d}"
        if model_cls is None or not model_cls.objects.filter(number=number).exists():
            return number
    raise RuntimeError(f"Could not allocate unique {prefix} record number.")
