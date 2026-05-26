from rest_framework import serializers
from .models import AssignmentRule, CategoryGroupMapping, UserSkill, SkillRequirement
from apps.teams.serializers import TeamSerializer
from apps.accounts.serializers import UserSerializer


class AssignmentRuleSerializer(serializers.ModelSerializer):
    target_group_details = TeamSerializer(source='target_group', read_only=True)
    target_user_details = UserSerializer(source='target_user', read_only=True)

    class Meta:
        model = AssignmentRule
        fields = [
            'id', 'name', 'order', 'conditions', 'target_group', 
            'target_group_details', 'target_user', 'target_user_details', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CategoryGroupMappingSerializer(serializers.ModelSerializer):
    team_details = TeamSerializer(source='team', read_only=True)

    class Meta:
        model = CategoryGroupMapping
        fields = ['id', 'category', 'subcategory', 'team', 'team_details', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserSkillSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = UserSkill
        fields = ['id', 'user', 'user_details', 'skill_name', 'proficiency', 'created_at']
        read_only_fields = ['id', 'created_at']


class SkillRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillRequirement
        fields = ['id', 'category', 'subcategory', 'skill_name', 'min_proficiency']
        read_only_fields = ['id']
