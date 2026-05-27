from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Workflow, WorkflowState, WorkflowTransition
from .serializers import WorkflowSerializer, WorkflowStateSerializer, WorkflowTransitionSerializer
from apps.common.mixins import OrgQuerysetMixin
from apps.common.permissions import IsAdminOrManager

class WorkflowViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = Workflow.objects.all()
    serializer_class = WorkflowSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    @action(detail=True, methods=['post'])
    def add_state(self, request, pk=None):
        workflow = self.get_object()
        serializer = WorkflowStateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workflow=workflow)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_transition(self, request, pk=None):
        workflow = self.get_object()
        serializer = WorkflowTransitionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workflow=workflow)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WorkflowStateViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = WorkflowState.objects.all()
    serializer_class = WorkflowStateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    
    def get_queryset(self):
        return WorkflowState.objects.filter(workflow__organization=self.request.organization)

class WorkflowTransitionViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    queryset = WorkflowTransition.objects.all()
    serializer_class = WorkflowTransitionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def get_queryset(self):
        return WorkflowTransition.objects.filter(workflow__organization=self.request.organization)
