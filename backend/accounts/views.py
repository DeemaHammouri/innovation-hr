from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError

from audit.events import client_ip, record_event

from . import ratelimit
from .authentication import Anonymous, check_csrf, clear_auth_cookies, issue_tokens, set_auth_cookies, user_from_refresh
from .models import ActionLog, Department, Role, User
from .passwords import generate_temporary_password
from .permissions import HasCapability, PasswordChangeNotPending
from .serializers import (
    ChangePasswordSerializer,
    DepartmentSerializer,
    PreferredLanguageSerializer,
    RoleSerializer,
    UserSerializer,
    UserWriteSerializer,
)

def log_action(request, user, action_name):
    ActionLog.objects.create(user=user, action=action_name, ip_address=client_ip(request))


MSG_TOO_MANY = "Too many sign-in attempts. Wait 5 minutes and try again."


class LoginView(APIView):
    """Sign in with a username or an email. The answer carries the user, never a token: the tokens arrive as HttpOnly cookies."""

    authentication_classes = [Anonymous]
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = str(request.data.get("identifier", request.data.get("email", ""))).strip().lower()
        password = str(request.data.get("password", ""))
        if not identifier or not password:
            return Response({"detail": "Enter your email or username and your password."}, status=status.HTTP_400_BAD_REQUEST)
        ip = client_ip(request) or ""
        if ratelimit.blocked(identifier, ip):
            record_event(request, "login_blocked", identifier=identifier)
            return Response({"detail": MSG_TOO_MANY}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            ratelimit.record_failure(identifier, ip)
            record_event(request, "login_failed", identifier=identifier)
            # Same answer for an unknown account, a wrong password and a deactivated account.
            return Response(
                {"detail": "That email or username and password don't match. Check them and try again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        ratelimit.clear(identifier)
        log_action(request, user, ActionLog.Action.LOGIN)
        record_event(request, "login_success", actor=user, target=user, identifier=identifier)
        response = Response({"user": UserSerializer(user).data})
        return set_auth_cookies(response, issue_tokens(user))


class RefreshView(APIView):
    """Swap the refresh cookie for a new pair. Each refresh token works once: the old one is blacklisted, so a stolen copy that is
    replayed after the real owner refreshed is refused."""

    authentication_classes = [Anonymous]
    permission_classes = [AllowAny]

    def post(self, request):
        check_csrf(request)
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw:
            raise AuthenticationFailed("Please sign in.", code="not_authenticated")
        refresh, user = user_from_refresh(raw)
        try:
            refresh.blacklist()
        except TokenError as exc:
            raise AuthenticationFailed("Your session has ended. Please sign in again.", code="token_revoked") from exc
        response = Response({"user": UserSerializer(user).data})
        return set_auth_cookies(response, issue_tokens(user), csrf=request.COOKIES.get(settings.AUTH_COOKIE_CSRF))


class LogoutView(APIView):
    """Works with an expired access token too: it retires the refresh token and clears the cookies."""

    authentication_classes = [Anonymous]
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw:
            check_csrf(request)
            try:
                refresh, user = user_from_refresh(raw)
                refresh.blacklist()
                log_action(request, user, ActionLog.Action.LOGOUT)
                record_event(request, "logout", actor=user, target=user)
            except (AuthenticationFailed, TokenError):
                pass  # already expired or used: the user is signed out either way
        return clear_auth_cookies(Response(status=status.HTTP_204_NO_CONTENT))


class MeView(APIView):
    # Usable while a password change is pending: it is how the page learns who is signed in.
    permission_classes = [HasCapability]
    required_capabilities = []

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        # Only the language preference. Every other field in the body is ignored.
        before = request.user.preferred_language
        serializer = PreferredLanguageSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(update_fields=["preferred_language"])
        if request.user.preferred_language != before:
            record_event(request, "language_changed", target=request.user, previous=before, chosen=request.user.preferred_language)
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Set a new password. Works while a password change is pending (the only thing besides /me and sign-out that does).
    The first change after a temporary password needs no current password; later ones do. Every old token stops working."""

    permission_classes = [HasCapability]
    required_capabilities = []

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        user.bump_token_version()
        record_event(request, "password_changed", actor=user, target=user)
        # The tokens held so far are now void: this device gets fresh ones and stays signed in.
        response = Response(UserSerializer(user).data)
        return set_auth_cookies(response, issue_tokens(user), csrf=request.COOKIES.get(settings.AUTH_COOKIE_CSRF))


class DepartmentListView(ListAPIView):
    required_capabilities = ["user.manage"]
    denied_message = "Only the CEO can do this."
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    pagination_class = None


class RoleListView(ListAPIView):
    """The roles a person can be given, optionally for one department (?department=ID). Super Admin is never offered."""

    required_capabilities = ["user.manage"]
    denied_message = "Only the CEO can do this."
    serializer_class = RoleSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Role.objects.exclude(key__in=["super_admin", "client"])
        department = self.request.query_params.get("department")
        return qs.filter(department_id=int(department)) if department and department.isdigit() else qs


class UserViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    required_capabilities = {"*": ["user.manage"]}
    denied_message = "Only the CEO can do this."
    queryset = User.objects.select_related("department", "role_ref").filter(is_superuser=False).exclude(role_ref__key__in=["super_admin", "client"])
    filter_backends = [SearchFilter]
    search_fields = ["full_name", "email", "department__name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        return UserSerializer if self.action in ("list", "retrieve") else UserWriteSerializer

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        p = self.request.query_params
        if p.get("department", "").isdigit():
            queryset = queryset.filter(department_id=int(p["department"]))
        if p.get("role"):
            queryset = queryset.filter(role_ref__key=p["role"])
        if p.get("status") in ("active", "inactive"):
            queryset = queryset.filter(is_active=p["status"] == "active")
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_event(request, "user_created", target=user, role=user.role_name, department=user.department.name)
        data = UserSerializer(user).data
        data["temporary_password"] = user.temporary_password  # shown once, here only
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        before = (user.role_name, user.department.name if user.department_id else "")
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        after = (user.role_name, user.department.name if user.department_id else "")
        record_event(request, "user_updated", target=user, from_role=before[0], to_role=after[0], from_department=before[1], to_department=after[1])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({"detail": "You can't deactivate your own account."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save()
        user.bump_token_version()
        record_event(request, "user_deactivated", target=user)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({"detail": "You can't change your own status."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = True
        user.save()
        record_event(request, "user_activated", target=user)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({"detail": "Change your own password from your profile."}, status=status.HTTP_400_BAD_REQUEST)
        temporary = generate_temporary_password()
        user.set_password(temporary)
        user.must_change_password = True
        user.save()
        user.bump_token_version()
        ratelimit.clear(user.email)
        record_event(request, "password_reset", target=user)
        return Response({"temporary_password": temporary})


class DashboardSummaryView(APIView):
    """Read-only numbers for the Home screen. What comes back depends on who is asking."""

    required_capabilities = []  # any signed-in person; what comes back depends on their capabilities

    @staticmethod
    def recent_clients(limit=5):
        from clients.models import Client

        rows = Client.objects.order_by("-created_at")[:limit]
        return [
            {"id": c.id, "company_name": c.company_name, "contact_person": c.contact_person, "created_at": c.created_at}
            for c in rows
        ]

    def get(self, request):
        from clients.models import Client

        user = request.user
        own = ActionLog.objects.filter(user=user, action=ActionLog.Action.LOGIN)[:5]
        data = {"my_sign_ins": [{"timestamp": log.timestamp} for log in own]}

        if user.has_capability("user.manage"):
            people = User.objects.filter(is_superuser=False)
            by_department = {row["department__name"]: row["n"] for row in people.values("department__name").annotate(n=Count("id"))}
            logins = ActionLog.objects.filter(action=ActionLog.Action.LOGIN, user__is_superuser=False).select_related("user")[:8]
            data["ceo"] = {
                "total_users": people.count(),
                "active_users": people.filter(is_active=True).count(),
                "pending_password_users": people.filter(must_change_password=True).count(),
                "users_by_department": [
                    {"department": d.name, "count": by_department.get(d.name, 0)} for d in Department.objects.all()
                ],
                "total_clients": Client.objects.count(),
                "recent_clients": self.recent_clients(),
                "recent_sign_ins": [
                    {"user_id": log.user_id, "full_name": log.user.full_name, "timestamp": log.timestamp} for log in logins
                ],
            }
        elif user.has_capability("operation.manage"):
            now = timezone.now()
            data["operation"] = {
                "total_clients": Client.objects.count(),
                "clients_this_month": Client.objects.filter(created_at__year=now.year, created_at__month=now.month).count(),
                "recent_clients": self.recent_clients(),
            }
        return Response(data)
