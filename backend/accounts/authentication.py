"""Cookie-based JWT sign-in.

The access and refresh tokens live only in HttpOnly cookies, so page scripts can never read them. Because browsers attach cookies
by themselves, every unsafe request (POST, PUT, PATCH, DELETE) must also prove it came from our own pages: it carries a CSRF token in
the `X-CSRF-Token` header that matches the readable `csrf_token` cookie (double-submit). Every token carries the user's
`token_version`; changing a password, resetting it, deactivating or changing the role bumps the version and cuts old tokens off.
"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Lower
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

SAFE = ("GET", "HEAD", "OPTIONS")
CSRF_HEADER = "HTTP_X_CSRF_TOKEN"


def issue_tokens(user):
    """A fresh refresh token stamped with the user's token_version; its access token inherits the claim."""
    refresh = RefreshToken.for_user(user)
    refresh["tv"] = user.token_version
    return refresh


def _cookie_kwargs(max_age, http_only, path="/"):
    return {
        "max_age": int(max_age.total_seconds()),
        "httponly": http_only,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": path,
    }


def set_auth_cookies(response, refresh, csrf=None):
    """Write the three cookies. Tokens are HttpOnly; the CSRF token is readable on purpose (the page copies it into a header)."""
    life = settings.SIMPLE_JWT
    response.set_cookie(settings.AUTH_COOKIE_ACCESS, str(refresh.access_token), **_cookie_kwargs(life["ACCESS_TOKEN_LIFETIME"], True, "/api/"))
    response.set_cookie(settings.AUTH_COOKIE_REFRESH, str(refresh), **_cookie_kwargs(life["REFRESH_TOKEN_LIFETIME"], True, settings.AUTH_REFRESH_COOKIE_PATH))
    response.set_cookie(settings.AUTH_COOKIE_CSRF, csrf or secrets.token_urlsafe(32), **_cookie_kwargs(life["REFRESH_TOKEN_LIFETIME"], False, "/"))
    return response


def clear_auth_cookies(response):
    for name, path in (
        (settings.AUTH_COOKIE_ACCESS, "/api/"),
        (settings.AUTH_COOKIE_REFRESH, settings.AUTH_REFRESH_COOKIE_PATH),
        (settings.AUTH_COOKIE_CSRF, "/"),
    ):
        response.delete_cookie(name, path=path, samesite=settings.AUTH_COOKIE_SAMESITE)
    return response


def check_csrf(request):
    cookie = request.COOKIES.get(settings.AUTH_COOKIE_CSRF, "")
    header = request.META.get(CSRF_HEADER, "")
    if not cookie or not header or not secrets.compare_digest(cookie.encode(), header.encode()):
        raise PermissionDenied(detail="Your session could not be verified. Reload the page and try again.", code="csrf_failed")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate_header(self, request):
        return 'Cookie realm="api"'  # makes DRF answer 401 (not 403) when nobody is signed in

    def authenticate(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw:
            return None
        try:
            token = self.get_validated_token(raw)
        except InvalidToken as exc:
            raise AuthenticationFailed("Your session has expired. Please sign in again.", code="token_expired") from exc
        user = self.get_user(token)
        if token.get("tv", -1) != user.token_version:
            raise AuthenticationFailed("Your session has ended. Please sign in again.", code="token_revoked")
        if request.method not in SAFE:
            check_csrf(request)
        return user, token


class Anonymous(BaseAuthentication):
    """For the sign-in endpoints: authenticates nobody, but makes failures answer 401 rather than 403."""

    def authenticate(self, request):
        return None

    def authenticate_header(self, request):
        return 'Cookie realm="api"'


def user_from_refresh(raw):
    """(refresh_token, user) for a valid, unused, current-version refresh cookie; raises AuthenticationFailed otherwise."""
    User = get_user_model()
    try:
        refresh = RefreshToken(raw)
    except TokenError as exc:
        raise AuthenticationFailed("Your session has expired. Please sign in again.", code="token_expired") from exc
    user = User.objects.filter(pk=refresh.get("user_id"), is_active=True).first()
    if user is None or refresh.get("tv", -1) != user.token_version:
        raise AuthenticationFailed("Your session has ended. Please sign in again.", code="token_revoked")
    return refresh, user


class IdentifierBackend:
    """Sign in with a username or an email address, ignoring case."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        User = get_user_model()
        ident = username.strip().lower()
        user = User.objects.annotate(_u=Lower("username"), _e=Lower("email")).filter(Q(_e=ident) | Q(_u=ident)).first()
        if user is None:
            User().set_password(password)  # same work for unknown identifiers, so timing does not reveal accounts
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return user.is_active

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id).first()
