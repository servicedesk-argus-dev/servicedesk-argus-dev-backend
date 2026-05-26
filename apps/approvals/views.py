from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ApprovalRequest, Approver
from .serializers import ApprovalRequestSerializer, ApproverSerializer
from .services import process_approval_action
from apps.common.mixins import OrgQuerysetMixin

class ApprovalRequestViewSet(OrgQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ApprovalRequest.objects.all()
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_pending(self, request):
        """
        Returns approvals where the current user is a pending approver.
        """
        pending_approvals = ApprovalRequest.objects.filter(
            organization=request.organization,
            approvers__user=request.user,
            approvers__state=Approver.State.PENDING,
            state=ApprovalRequest.State.PENDING
        ).distinct()
        
        page = self.paginate_queryset(pending_approvals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(pending_approvals, many=True)
        return Response(serializer.data)

class ApproverViewSet(viewsets.GenericViewSet):
    queryset = Approver.objects.all()
    serializer_class = ApproverSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        approver = self.get_object()
        if approver.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            process_approval_action(approver.id, 'APPROVE', request.data.get('comments', ''))
            return Response({"status": "approved"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        approver = self.get_object()
        if approver.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            process_approval_action(approver.id, 'REJECT', request.data.get('comments', ''))
            return Response({"status": "rejected"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
