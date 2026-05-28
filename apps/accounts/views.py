from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.pagination import DefaultPagination
from apps.common.permissions import (
    Roles,
    ROLE_TOKEN_NAMES,
    canonical_role_name,
    can_manage_users,
    can_manage_service_desk,
    is_service_desk_staff,
    permission_code_from_keycloak_role,
    role_token_name,
    user_has_permission,
)
from apps.common.responses import failure, success
from apps.common.audit import create_audit_log
from .models import Role, Permission
from .serializers import (
    ChangePasswordSerializer,
    ManagedUserCreateSerializer,
    ManagedUserUpdateSerializer,
    MeSerializer,
    PasswordSetSerializer,
    PermissionSerializer,
    ProfileUpdateSerializer,
    RoleSerializer,
    SignupSerializer,
    UserSerializer,
)

User = get_user_model()


def _extract_keycloak_roles(claims):
    roles = set(claims.get("realm_access", {}).get("roles", []) or [])
    resource_access = claims.get("resource_access", {}) or {}
    for client_roles in resource_access.values():
        roles.update(client_roles.get("roles", []) or [])
    return sorted(str(role).strip() for role in roles if str(role).strip())


def _sync_keycloak_claims(user, claims):
    from django.conf import settings
    from django.utils import timezone

    raw_roles = _extract_keycloak_roles(claims)
    permission_codes = sorted(
        code for code in (permission_code_from_keycloak_role(role) for role in raw_roles) if code
    )
    role_names = sorted(
        {
            canonical_role_name(role)
            for role in raw_roles
            if role_token_name(role) in ROLE_TOKEN_NAMES
        }
    )

    user.keycloak_subject = claims.get("sub") or user.keycloak_subject or ""
    user.keycloak_roles = raw_roles
    user.keycloak_permissions = permission_codes
    user.keycloak_last_sync = timezone.now()
    user.save(
        update_fields=[
            "keycloak_subject",
            "keycloak_roles",
            "keycloak_permissions",
            "keycloak_last_sync",
            "updated_at",
        ]
    )

    if getattr(settings, "KEYCLOAK_SYNC_LOCAL_ROLES", False) and role_names:
        from .serializers import ensure_role

        user.roles.set([ensure_role(role_name) for role_name in role_names])


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all().order_by('code')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not user_has_permission(request.user, "*:*"):
            raise PermissionDenied("Only a Super Admin can view permissions.")


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not user_has_permission(request.user, "*:*"):
            raise PermissionDenied("Only a Super Admin can manage roles and permissions.")

    def get_queryset(self):
        return Role.objects.all().order_by('name')

    def perform_create(self, serializer):
        serializer.save()


def _token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _ensure_user_organization(user):
    return getattr(user, "organization_id", None) is not None or is_service_desk_staff(user)


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            print(f"Signup validation errors: {serializer.errors}")
            return failure(
                "Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )
        user = serializer.save()
        if not _ensure_user_organization(user):
            return failure("user must belong to an organization", status_code=400)
        tokens = _token_payload(user)
        return success(
            {"user": MeSerializer(user).data, **tokens},
            "user created",
            201,
        )


class AuthIndexView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return success(
            {
                "endpoints": {
                    "signup": "/api/v1/auth/signup",
                    "login": "/api/v1/auth/login",
                    "logout": "/api/v1/auth/logout",
                    "refresh": "/api/v1/auth/refresh",
                    "me": "/api/v1/auth/me",
                    "users": "/api/v1/auth/users/",
                }
            }
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")
        if not username or not password:
            return failure("username/email and password are required", status_code=400)

        user = authenticate(request, username=username, password=password)
        if not user and "@" in username:
            try:
                user_obj = User.objects.get(email__iexact=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass

        if not user:
            create_audit_log(
                request, "LOGIN_FAILED", "USER", 
                description=f"Failed login attempt for {username}"
            )
            return failure("invalid credentials", status_code=401)

        if not user.is_active_member:
            return failure("account is disabled", status_code=403)

        if not _ensure_user_organization(user):
            return failure("user does not have organization access", status_code=403)

        if user.mfa_enabled:
            code = request.data.get("code") or request.data.get("mfaToken")
            if not code:
                return success(
                    {"mfa_required": True, "requiresMfa": True, "userId": str(user.id)}, 
                    "MFA verification required"
                )
            
            if not verify_totp(user.mfa_secret, code):
                create_audit_log(
                    request, "MFA_FAILED", "USER", 
                    resource_id=user.id, 
                    description=f"Invalid MFA code for user {user.username}",
                    organization=user.organization
                )
                return failure("invalid MFA code", status_code=401)

        create_audit_log(
            request, "LOGIN_SUCCESS", "USER", 
            resource_id=user.id, 
            description=f"User {user.username} logged in successfully",
            organization=user.organization
        )
        payload = _token_payload(user)
        return success({"user": MeSerializer(user).data, **payload}, "login successful")


_keycloak_jwks_client = None


def _get_keycloak_jwks_client():
    """Lazy singleton; PyJWKClient caches fetched JWKS internally."""
    global _keycloak_jwks_client
    if _keycloak_jwks_client is None:
        from django.conf import settings
        from jwt import PyJWKClient

        jwks_url = getattr(settings, "KEYCLOAK_JWKS_URL", "").strip()
        if not jwks_url:
            raise RuntimeError("KEYCLOAK_JWKS_URL not configured")
        _keycloak_jwks_client = PyJWKClient(jwks_url)
    return _keycloak_jwks_client


def _verify_keycloak_token(token):
    """Verify a Keycloak-issued JWT against the realm JWKS and return claims."""
    import jwt
    from django.conf import settings

    signing_key = _get_keycloak_jwks_client().get_signing_key_from_jwt(token).key
    issuer = getattr(settings, "KEYCLOAK_ISSUER", "").strip() or None
    return jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        issuer=issuer,
        # Keycloak audience can vary by client setup. Verify signature + issuer
        # and keep audience checking out of this exchange endpoint.
        options={"verify_aud": False},
    )


class KeycloakLoginView(APIView):
    """
    Frontend posts the Keycloak access token received after the OIDC code flow.
    We verify it, find or create the matching Django user, and return local JWTs.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get("accessToken") or request.data.get("access_token")
        if not access_token:
            return failure("accessToken required", status_code=400)

        try:
            claims = _verify_keycloak_token(access_token)
        except Exception as exc:
            create_audit_log(
                request,
                "KEYCLOAK_LOGIN_FAILED",
                "USER",
                description=f"Keycloak token verification failed: {exc}",
            )
            return failure("invalid Keycloak token", status_code=401)

        email = (claims.get("email") or claims.get("preferred_username") or "").lower().strip()
        if not email:
            return failure("Keycloak token has no email/preferred_username", status_code=400)

        from django.conf import settings
        from apps.organizations.models import Organization

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            if not getattr(settings, "KEYCLOAK_AUTO_CREATE_USERS", False):
                return failure(f"no local user for {email}", status_code=403)

            default_org_slug = getattr(settings, "KEYCLOAK_DEFAULT_CLIENT_ORG", "").strip() or "default-org"
            default_org = Organization.objects.filter(slug=default_org_slug).first()
            user = User.objects.create(
                username=email,
                email=email,
                first_name=claims.get("given_name") or "",
                last_name=claims.get("family_name") or "",
                organization=default_org,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()

        _sync_keycloak_claims(user, claims)

        if not user.is_active or not user.is_active_member:
            return failure("account is disabled", status_code=403)

        if not _ensure_user_organization(user):
            return failure("user does not have organization access", status_code=403)

        create_audit_log(
            request,
            "KEYCLOAK_LOGIN_SUCCESS",
            "USER",
            resource_id=user.id,
            description=f"Keycloak SSO login for {user.username}",
            organization=user.organization,
        )
        payload = _token_payload(user)
        return success({"user": MeSerializer(user).data, **payload}, "login successful")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refreshToken") or request.data.get("refresh")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass
        return success(message="logout successful")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success(MeSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(MeSerializer(request.user).data, "profile updated")


import secrets
from datetime import timedelta
from django.utils import timezone
from .models import PasswordResetToken, UserInvitation
from apps.notifications.tasks import send_email_task

class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return failure("Email is required.", status_code=400)

        user = User.objects.filter(email__iexact=email).first()
        if user:
            # Create token
            token = secrets.token_urlsafe(32)
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Send email
            base_url = request.headers.get('Origin') or 'http://localhost:3000'
            create_audit_log(
                request, "PASSWORD_RESET_REQUESTED", "USER", 
                resource_id=user.id, 
                description=f"Password reset link sent to {user.email}"
            )
            send_email_task.delay(
                recipient_email=user.email,
                subject="Reset Your Argus Password",
                template_name='email/password_reset.html',
                context={
                    'username': user.username,
                    'reset_link': f"{base_url}/reset-password?token={token}",
                }
            )

        # Success message even if user not found (security)
        return success(message="If an account exists with this email, you will receive a reset link shortly.")


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token")
        new_password = request.data.get("password")
        
        if not token_str or not new_password:
            return failure("Token and password are required.", status_code=400)

        reset_token = PasswordResetToken.objects.filter(
            token=token_str, 
            used=False, 
            expires_at__gt=timezone.now()
        ).first()

        if not reset_token:
            return failure("Invalid or expired reset token.", status_code=400)

        user = reset_token.user
        user.set_password(new_password)
        user.save()

        create_audit_log(
            request, "PASSWORD_RESET_SUCCESS", "USER", 
            resource_id=user.id, 
            description=f"User {user.username} reset their password"
        )

        reset_token.used = True
        reset_token.save()

        return success(message="Password reset successful. You can now log in with your new password.")


class InviteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.has_role("Super Admin") or request.user.has_role("Org Admin") or request.user.has_role("Manager")):
            return failure("Only admins and managers can invite users.", status_code=403)

        organization = getattr(request, "organization", None)
        if organization is None:
            return failure("Organization context required.", status_code=400)

        email = request.data.get("email")
        role_name = request.data.get("role", "Engineer")
        role = Role.objects.filter(name=role_name).first()
        
        if not email:
            return failure("Email is required.", status_code=400)

        # Check if user already exists
        if User.objects.filter(email__iexact=email).exists():
            return failure("A user with this email already exists.", status_code=400)

        # Create invitation
        token = secrets.token_urlsafe(32)
        invitation = UserInvitation.objects.create(
            email=email,
            organization=organization,
            invited_by=request.user,
            token=token,
            expires_at=timezone.now() + timedelta(days=2)
        )
        if role:
            invitation.roles.add(role)
        
        create_audit_log(
            request, "USER_INVITED", "USER_INVITATION", 
            description=f"Invited {email} with role {role_name}"
        )
        
        # Send email
        base_url = request.headers.get('Origin') or 'http://localhost:3000'
        send_email_task.delay(
            recipient_email=email,
            subject=f"Invitation to join {organization.name} on Argus",
            template_name='email/user_invite.html',
            context={
                'inviter_name': request.user.get_full_name() or request.user.username,
                'organization_name': organization.name,
                'role': role_name,
                'invite_link': f"{base_url}/accept-invite?token={token}",
            }
        )

        return success(message=f"Invitation sent to {email}.")


class AcceptInviteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token")
        username = request.data.get("username")
        password = request.data.get("password")
        first_name = request.data.get("firstName")
        last_name = request.data.get("lastName")

        if not token_str or not username or not password:
            return failure("Token, username, and password are required.", status_code=400)

        invitation = UserInvitation.objects.filter(
            token=token_str, 
            accepted=False, 
            expires_at__gt=timezone.now()
        ).first()

        if not invitation:
            return failure("Invalid or expired invitation token.", status_code=400)

        # Create user
        user = User.objects.create_user(
            username=username,
            email=invitation.email,
            password=password,
            first_name=first_name or "",
            last_name=last_name or "",
            organization=invitation.organization
        )
        for r in invitation.roles.all():
            user.roles.add(r)

        invitation.accepted = True
        invitation.save()

        create_audit_log(
            request, "INVITE_ACCEPTED", "USER", 
            resource_id=user.id, 
            description=f"User {user.username} joined the organization via invitation"
        )

        tokens = _token_payload(user)
        return success(
            {"user": MeSerializer(user).data, **tokens},
            "Invitation accepted. Welcome to Argus!",
            201
        )


from .mfa import generate_mfa_secret, get_totp_uri, generate_qr_code_base64, verify_totp

class MFASetupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.mfa_enabled:
            return failure("MFA is already enabled.", status_code=400)

        # Generate or reuse secret
        if not user.mfa_secret:
            user.mfa_secret = generate_mfa_secret()
            user.save(update_fields=["mfa_secret", "updated_at"])

        uri = get_totp_uri(user, user.mfa_secret)
        qr_code = generate_qr_code_base64(uri)

        return success({
            "secret": user.mfa_secret,
            "qrCode": f"data:image/png;base64,{qr_code}",
            "uri": uri
        })

    def post(self, request):
        user = request.user
        code = request.data.get("code")
        if not code:
            return failure("Verification code is required.", status_code=400)

        if not user.mfa_secret:
            return failure("MFA setup not initialized. Call GET first.", status_code=400)

        if verify_totp(user.mfa_secret, code):
            user.mfa_enabled = True
            user.save(update_fields=["mfa_enabled", "updated_at"])
            
            create_audit_log(
                request, "MFA_ENABLED", "USER", 
                resource_id=user.id, 
                description=f"User {user.username} enabled MFA"
            )
            
            return success(message="MFA enabled successfully.")
        else:
            return failure("Invalid verification code.", status_code=400)


class MFADisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        code = request.data.get("code")
        if not code:
            return failure("Verification code is required to disable MFA.", status_code=400)

        if verify_totp(user.mfa_secret, code):
            user.mfa_enabled = False
            user.mfa_secret = None
            user.save(update_fields=["mfa_enabled", "mfa_secret", "updated_at"])
            
            create_audit_log(
                request, "MFA_DISABLED", "USER", 
                resource_id=user.id, 
                description=f"User {user.username} disabled MFA"
            )
            
            return success(message="MFA disabled successfully.")
        else:
            return failure("Invalid verification code.", status_code=400)


def _manageable_user_queryset(request):
    queryset = User.objects.all().select_related("organization").prefetch_related("roles")
    if is_service_desk_staff(request.user):
        org_id = request.query_params.get("organization") or request.query_params.get("organization_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset
    organization = getattr(request, "organization", None)
    if organization is None:
        return User.objects.none()
    return queryset.filter(organization=organization)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination

    def get(self, request):
        users = _manageable_user_queryset(request)

        search = request.query_params.get("search")
        if search:
            users = users.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(organization__name__icontains=search)
            )

        role = request.query_params.get("role")
        role_aliases = {
            "ADMIN": [Roles.SUPER_ADMIN, Roles.ORG_ADMIN],
            "MANAGER": [Roles.MANAGER, Roles.TEAM_LEAD],
            "ENGINEER": [Roles.ENGINEER],
            "OPERATOR": [Roles.NOC, Roles.OPERATOR],
            "CLIENT": [Roles.CLIENT_USER],
            "VIEWER": [Roles.VIEWER],
        }
        if role and role != "ALL":
            users = users.filter(roles__name__in=role_aliases.get(role, [role])).distinct()

        status = request.query_params.get("status")
        if status == "ACTIVE":
            users = users.filter(is_active=True, is_active_member=True)
        elif status in {"INACTIVE", "LOCKED"}:
            users = users.filter(Q(is_active=False) | Q(is_active_member=False))

        users = users.order_by("organization__name", "first_name", "last_name", "email")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)
        serializer = UserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not can_manage_users(request.user):
            return failure("Only admins and managers can create accounts.", status_code=403)

        data = request.data.copy()
        if not is_service_desk_staff(request.user):
            data["organization_id"] = str(request.organization_id)

        serializer = ManagedUserCreateSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return failure("Validation failed.", errors=serializer.errors, status_code=400)
        try:
            user = serializer.save()
        except serializers.ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)
        create_audit_log(
            request,
            "USER_CREATED",
            "USER",
            resource_id=user.id,
            description=f"Created account for {user.email}",
            organization=user.organization,
        )
        return success(UserSerializer(user).data, "user created", 201)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_user(self, request, pk):
        return _manageable_user_queryset(request).filter(pk=pk).first()

    def get(self, request, pk):
        if not can_manage_service_desk(request.user) and str(request.user.id) != str(pk):
            return failure("Access denied.", status_code=403)

        user = self._get_user(request, pk)
        if not user:
            return failure("User not found.", status_code=404)

        return success(UserSerializer(user).data)

    def patch(self, request, pk):
        if not can_manage_service_desk(request.user):
            return failure("Only admins, NOC, and team leads can update users.", status_code=403)

        user = self._get_user(request, pk)
        if not user:
            return failure("User not found.", status_code=404)

        data = request.data.copy()
        if not is_service_desk_staff(request.user):
            data.pop("organization_id", None)
        serializer = ManagedUserUpdateSerializer(user, data=data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return failure("Validation failed.", errors=serializer.errors, status_code=400)
        try:
            user = serializer.save()
        except serializers.ValidationError as exc:
            return failure("Validation failed.", errors=exc.detail, status_code=400)
        return success(UserSerializer(user).data, "user updated")

    def delete(self, request, pk):
        if not can_manage_service_desk(request.user):
            return failure("Only admins can deactivate users.", status_code=403)

        user = self._get_user(request, pk)
        if not user:
            return failure("User not found.", status_code=404)

        user.is_active_member = False
        user.is_active = False
        user.save(update_fields=["is_active_member", "is_active", "updated_at"])
        return success(UserSerializer(user).data, "user deactivated")


class UserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not can_manage_service_desk(request.user):
            return failure("Only admins, NOC, and team leads can reset passwords.", status_code=403)

        user = _manageable_user_queryset(request).filter(pk=pk).first()
        if not user:
            return failure("User not found.", status_code=404)

        serializer = PasswordSetSerializer(data=request.data)
        if not serializer.is_valid():
            return failure("Validation failed.", errors=serializer.errors, status_code=400)
        user.set_password(serializer.validated_data["password"])
        user.must_change_password = serializer.validated_data["must_change_password"]
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        return success(UserSerializer(user).data, "password reset")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data["current_password"]
        if not request.user.must_change_password and not request.user.check_password(current_password):
            return failure("Current password is incorrect.", status_code=400)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password", "updated_at"])
        return success(UserSerializer(request.user).data, "password changed")
