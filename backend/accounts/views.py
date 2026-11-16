import secrets

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

from . import ratelimit
from .authentication import Anonymous, check_csrf, clear_auth_cookies, issue_tokens, set_auth_cookies, user_from_refresh
from .models import ActionLog, Department, User
from .permissions import HasCapability, PasswordChangeNotPending
from .serializers import (
    ChangePasswordSerializer,
    DepartmentSerializer,
    PreferredLanguageSerializer,
    UserSerializer,
    UserWriteSerializer,
)

# No look-alike characters (0/O, 1/l/I) so a temporary password is easy to read out loud.
PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def client_ip(request):
    """The caller's address. X-Forwarded-For is honoured only when the deployment says a trusted proxy sets it (anyone can forge it)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded and getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, user, action_name):
    ActionLog.objects.create(user=user, action=action_name, ip_address=client_ip(request))


MSG_TOO_MANY = "Too many sign-in attempts. Wait 15 minutes and try again."


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
            return Response({"detail": MSG_TOO_MANY}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            ratelimit.record_failure(identifier, ip)
            # Same answer for an unknown account, a wrong password and a deactivated account.
            return Response(
                {"detail": "That email or username and password don't match. Check them and try again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        ratelimit.clear(identifier)
        log_action(request, user, ActionLog.Action.LOGIN)
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
        serializer = PreferredLanguageSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(update_fields=["preferred_language"])
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Forced change only: the user has just signed in with a temporary password."""

    permission_classes = [HasCapability]
    required_capabilities = []

    def post(self, request):
        user = request.user
        if not user.must_change_password:
            return Response({"detail": "Your password is already set."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        return Response(UserSerializer(user).data)


class DepartmentListView(ListAPIView):
    required_capabilities = ["user.manage"]
    denied_message = "Only the CEO can do this."
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    pagination_class = None


class UserViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    required_capabilities = {"*": ["user.manage"]}
    denied_message = "Only the CEO can do this."
    queryset = User.objects.select_related("department").filter(is_superuser=False)
    filter_backends = [SearchFilter]
    search_fields = ["full_name", "email", "department__name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        return UserSerializer if self.action in ("list", "retrieve") else UserWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(UserSerializer(serializer.save()).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({"detail": "You can't deactivate your own account."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        temporary = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(10))
        user.set_password(temporary)
        user.must_change_password = True
        user.save()
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
