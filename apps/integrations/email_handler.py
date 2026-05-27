import re
from apps.incidents.models import Incident
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.common.utils import generate_record_number

def handle_inbound_email(subject, body, from_email):
    """
    Processes an inbound email to create or update records.
    Simplified version of ServiceNow's Inbound Email Actions.
    """
    # 1. Identify User
    user = User.objects.filter(email=from_email).first()
    if not user:
        # For now, if user doesn't exist, we can't process
        # In a real system, we might create a guest user or ignore
        return None
        
    organization = user.organization
    
    # 2. Check if this is a reply to an existing incident
    # Look for "INC" + number in subject
    match = re.search(r'(INC\d+)', subject)
    if match:
        inc_number = match.group(1)
        incident = Incident.objects.filter(number=inc_number, organization=organization).first()
        if incident:
            # Add body as a work note
            from apps.incidents.models import WorkNote
            WorkNote.objects.create(
                incident=incident,
                author=user,
                content=f"Email Reply from {from_email}:\n\n{body}",
                source="EMAIL"
            )
            return incident

    # 3. If no match, create a new incident
    incident = Incident.objects.create(
        number=generate_record_number("INC", organization, "last_incident_number"),
        short_description=subject,
        description=body,
        created_by=user,
        organization=organization,
        source="EMAIL"
    )
    
    return incident
