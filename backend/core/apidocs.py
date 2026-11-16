"""OpenAPI schema and the Swagger / ReDoc pages. Closed to everyone without `settings.manage`, like every other endpoint."""
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


class SchemaView(SpectacularAPIView):
    required_capabilities = ["settings.manage"]


class SwaggerView(SpectacularSwaggerView):
    required_capabilities = ["settings.manage"]


class RedocView(SpectacularRedocView):
    required_capabilities = ["settings.manage"]


from drf_spectacular.extensions import OpenApiAuthenticationExtension  # noqa: E402


class CookieJWTScheme(OpenApiAuthenticationExtension):
    """Tokens travel in an HttpOnly cookie; unsafe methods also need the X-CSRF-Token header (see the description)."""

    target_class = "accounts.authentication.CookieJWTAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "HttpOnly cookie set by POST /auth/login/. POST, PUT, PATCH and DELETE must also send the csrf_token cookie value in the X-CSRF-Token header.",
        }


def only_v1(endpoints, **kwargs):
    """The /api/ alias serves the same routes as /api/v1/; document the contract once."""
    return [e for e in endpoints if e[0].startswith("/api/v1/")]


from core import apidocs_specs  # noqa: E402,F401  (applies the documentation decorators to the views)
