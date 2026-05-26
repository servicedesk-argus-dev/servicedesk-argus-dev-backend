import uuid
from django.contrib.auth.models import AbstractUser, Permission as DjangoPermission
from django.db import models


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=100, unique=True, db_index=True)  # e.g., 'incident.create'
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        ordering = ["code"]

    def __str__(self):
        return self.code

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)  # For core roles like Super Admin
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"
        ordering = ["name"]

    def __str__(self):
        return self.name

class User(AbstractUser):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    
    # Metadata for production
    is_active_member = models.BooleanField(default=True)
    avatar_url = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    timezone = models.CharField(max_length=50, default="UTC")
    notification_prefs = models.JSONField(default=dict, blank=True)
    must_change_password = models.BooleanField(default=False)
    keycloak_subject = models.CharField(max_length=255, blank=True, default="", db_index=True)
    keycloak_roles = models.JSONField(default=list, blank=True)
    keycloak_permissions = models.JSONField(default=list, blank=True)
    keycloak_last_sync = models.DateTimeField(null=True, blank=True)
    
    # MFA
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def has_role(self, role_name):
        target = str(role_name).replace("_", " ").replace("-", " ").casefold()
        return any(
            str(name).replace("_", " ").replace("-", " ").casefold() == target
            for name in self.roles.values_list("name", flat=True)
        )

    @property
    def role_names(self):
        return list(self.roles.values_list('name', flat=True))

    class Meta:
        db_table = "users"


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_tokens"
        ordering = ["-created_at"]


class UserInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    roles = models.ManyToManyField(Role, related_name="invitations", blank=True)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="invitations")
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sent_invitations")
    token = models.CharField(max_length=64, unique=True)
    accepted = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_invitations"
        ordering = ["-created_at"]

