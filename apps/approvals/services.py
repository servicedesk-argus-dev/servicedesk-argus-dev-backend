from django.utils import timezone
from apps.approvals.models import ApprovalRequest, Approver

def create_approval_request(obj, title, approver_users, description=""):
    """
    Creates a new approval request for an object.
    """
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(obj)
    
    request = ApprovalRequest.objects.create(
        organization=obj.organization,
        content_type=content_type,
        object_id=obj.id,
        title=title,
        description=description
    )
    
    for user in approver_users:
        Approver.objects.create(
            request=request,
            user=user
        )
        
    return request

def process_approval_action(approver_id, action, comments=""):
    """
    Handles an approver's action (APPROVE/REJECT).
    """
    approver = Approver.objects.get(id=approver_id)
    if approver.state != Approver.State.PENDING:
        raise ValueError("This approval has already been actioned.")
        
    approver.state = Approver.State.APPROVED if action == 'APPROVE' else Approver.State.REJECTED
    approver.comments = comments
    approver.actioned_at = timezone.now()
    approver.save()
    
    # Check if the entire request is now approved or rejected
    request = approver.request
    all_approvers = request.approvers.all()
    
    if action == 'REJECT':
        request.state = ApprovalRequest.State.REJECTED
        request.save()
        # Trigger rejection logic for the target object...
    elif all(a.state == Approver.State.APPROVED for a in all_approvers):
        request.state = ApprovalRequest.State.APPROVED
        request.save()
        # Trigger approval logic for the target object...
        
    return approver
