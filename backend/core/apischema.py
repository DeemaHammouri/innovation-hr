"""Schema-generation helpers for drf-spectacular (settings point here; kept apart from core.apidocs, which imports the views)."""

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import build_basic_type, build_parameter_type, get_view_model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter


class ApiAutoSchema(AutoSchema):
    """Plain ViewSets have no queryset to read the id type from: every id in this API is an integer, so say so instead of guessing."""

    ID_NAMES = ("id", "pk")

    def _paginates(self):
        """Only a viewset's `list` action is paginated; a custom action that returns a list (history, interactions, assignees) is not."""
        action = getattr(self.view, "action", None)
        return action in (None, "list")

    def _get_paginator(self):
        return super()._get_paginator() if self._paginates() else None

    def get_filter_backends(self):
        # Filters narrow the list and the board; they mean nothing on a one-record action that happens to return rows.
        if not self._paginates() and getattr(self.view, "detail", False):
            return []
        return super().get_filter_backends()

    def _resolve_path_parameters(self, variables):
        if get_view_model(self.view, emit_warnings=False) is not None:
            return super()._resolve_path_parameters(variables)
        known = [v for v in variables if v in self.ID_NAMES]
        others = [v for v in variables if v not in self.ID_NAMES]
        found = [
            build_parameter_type(name=v, location=OpenApiParameter.PATH, description="Record id.", schema=build_basic_type(OpenApiTypes.INT))
            for v in known
        ]
        return found + (super()._resolve_path_parameters(others) if others else [])


ERROR_DESCRIPTIONS = {
    "400": "Validation failed. `error.fields` maps each field to its messages.",
    "401": "Not signed in, or the session has ended.",
    "403": "Signed in but not allowed to do this.",
    "404": "The record does not exist or is not visible to this person.",
    "429": "Too many attempts.",
}


def error_envelope(result, generator, request, public):
    """Every error leaves the API as {"error": {"code", "message", "fields"?}} (core/errors.py): say so once and reference it from each operation."""
    schemas = result.setdefault("components", {}).setdefault("schemas", {})
    schemas["ErrorEnvelope"] = {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string", "description": "Stable key such as validation_error, not_authenticated, permission_denied, not_found, conflict, rate_limited, server_error."},
                "message": {"type": "string", "description": "Plain-language sentence for the person."},
                "fields": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "description": "Per-field messages, present on validation errors."},
            },
        }},
    }
    ref = {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}}
    for path, item in result.get("paths", {}).items():
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            codes = ["401", "403"] if op.get("security") else ["403"]
            if method in ("post", "put", "patch") or any(p.get("in") == "query" for p in op.get("parameters", [])):
                codes.append("400")
            if any(p.get("in") == "path" for p in op.get("parameters", [])):
                codes.append("404")
            if path.endswith("/login/"):
                codes += ["401", "429"]
            responses = op.setdefault("responses", {})
            for code in dict.fromkeys(codes):
                responses.setdefault(code, {"description": ERROR_DESCRIPTIONS[code], "content": ref})
    return result
