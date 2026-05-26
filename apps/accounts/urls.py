from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    AuthIndexView, KeycloakLoginView, LoginView, LogoutView, MeView, RefreshView,
    SignupView, UserListView, ForgotPasswordView, ResetPasswordView,
    InviteUserView, AcceptInviteView, UserDetailView,
    MFASetupView, MFADisableView, RoleViewSet, PermissionViewSet,
    UserResetPasswordView, ChangePasswordView,
)

router = SimpleRouter(trailing_slash=False)
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"permissions", PermissionViewSet, basename="permission")

urlpatterns = [
    path("", AuthIndexView.as_view()),
    path("", include(router.urls)),
    path("signup", SignupView.as_view()),
    path("register", SignupView.as_view()),
    path("login", LoginView.as_view()),
    path("keycloak-login", KeycloakLoginView.as_view()),
    path("keycloak-login/", KeycloakLoginView.as_view()),
    path("logout", LogoutView.as_view()),
    path("refresh", RefreshView.as_view()),
    path("me", MeView.as_view()),
    path("forgot-password", ForgotPasswordView.as_view()),
    path("reset-password", ResetPasswordView.as_view()),
    path("change-password", ChangePasswordView.as_view()),
    path("invite", InviteUserView.as_view()),
    path("accept-invite", AcceptInviteView.as_view()),
    path("mfa/setup", MFASetupView.as_view()),
    path("mfa/disable", MFADisableView.as_view()),
    # Users list — used by IncidentCreate / assignment dropdowns
    path("users", UserListView.as_view()),
    path("users/", UserListView.as_view()),
    path("users/<uuid:pk>", UserDetailView.as_view()),
    path("users/<uuid:pk>/", UserDetailView.as_view()),
    path("users/<uuid:pk>/reset-password", UserResetPasswordView.as_view()),
    path("users/<uuid:pk>/reset-password/", UserResetPasswordView.as_view()),
]
