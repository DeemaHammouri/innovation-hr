"""Walks every URL the API exposes and tries every method as anonymous and as each of the eight roles.

Used by core/tests_hardening.py. The checks are the ones that catch a forgotten permission class: an endpoint that answers an anonymous
caller, or any request that ends in a server error. `matrix()` returns the raw table for docs/PERMISSIONS.md.
"""
import re

from django.urls import URLPattern, URLResolver, get_resolver

from .roles import ALL_ROLES

METHODS = ("get", "post", "put", "patch", "delete")
SAMPLES = {"int": "1", "str": "x", "slug": "x", "uuid": "00000000-0000-0000-0000-000000000001"}

# Endpoints an anonymous caller may reach on purpose (the sign-in flow and the health check). Everything else must refuse.
PUBLIC = {
    ("post", "/api/auth/login/"),
    ("post", "/api/auth/refresh/"),
    ("get", "/api/health/"),
}


def _walk(patterns, prefix=""):
    for p in patterns:
        route = str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + route)
        elif isinstance(p, URLPattern):
            yield prefix + route, p


def endpoints():
    """[(concrete_url, template)] for every API route. Regex routes from DRF routers are turned into sample URLs."""
    out, seen = [], set()
    for template, _ in _walk(get_resolver().url_patterns):
        if not template.startswith("api/"):
            continue
        url = "/" + template
        url = re.sub(r"<(\w+):\w+>", lambda m: SAMPLES.get(m.group(1), "1"), url)
        url = re.sub(r"\(\?P<\w+>[^)]*\)", "1", url)
        url = url.replace("^", "").replace("$", "").replace("\\.(?P<format>[a-z0-9]+)/?", "").replace("/?", "/")
        url = re.sub(r"//+", "/", url)
        if "(" in url or "\\" in url or url in seen:
            continue
        seen.add(url)
        out.append((url, template))
    return sorted(out)


def call(client, method, url):
    fn = getattr(client, method)
    return fn(url) if method in ("get", "delete") else fn(url, {}, format="json")


def matrix(test):
    """Run everything; returns {(method, url): {"anon": code, role: code, ...}}."""
    table = {}
    for url, _ in endpoints():
        for method in METHODS:
            row = {}
            test.client.force_authenticate(None)
            row["anon"] = call(test.client, method, url).status_code
            for role in ALL_ROLES:
                test.as_role(role)
                row[role] = call(test.client, method, url).status_code
            table[(method, url)] = row
    test.client.force_authenticate(None)
    return table
