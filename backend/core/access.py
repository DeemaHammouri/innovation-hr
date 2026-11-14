"""
Which records can carry an activity trail, comments and files, and who may see or change them.

Every module registers its record type once. The generic endpoints (activity, comments, files) then
check the PARENT record's rule, so a file or comment can never be reached by someone who cannot reach its record.
A target is written "<key>:<id>", for example "client:5".
"""
from dataclasses import dataclass
from typing import Callable, Optional

from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import NotFound, ValidationError


@dataclass
class Target:
    key: str
    model: type
    can_view: Callable  # (user, obj) -> bool
    can_write: Callable  # (user, obj) -> bool
    can_attach: Optional[Callable] = None  # (user, obj, category) -> bool; defaults to can_write
    can_comment: Optional[Callable] = None  # (user, obj) -> bool; defaults to can_view
    label: Optional[Callable] = None  # obj -> short human title, for notifications and search
    link: Optional[Callable] = None  # obj -> frontend path

    def may_attach(self, user, obj, category=""):
        return (self.can_attach or (lambda u, o, c: self.can_write(u, o)))(user, obj, category)

    def may_comment(self, user, obj):
        return (self.can_comment or self.can_view)(user, obj)


_REGISTRY = {}


def register(key, model, can_view, can_write, **extra):
    _REGISTRY[key] = Target(key, model, can_view, can_write, **extra)


def target_for(key):
    try:
        return _REGISTRY[key]
    except KeyError:
        raise ValidationError({"target": "Unknown record type."})


def target_key_for(obj):
    for key, t in _REGISTRY.items():
        if isinstance(obj, t.model):
            return key
    raise ValueError(f"{obj.__class__.__name__} is not registered in core.access")


def target_for_model(model):
    for t in _REGISTRY.values():
        if t.model is model:
            return t
    raise NotFound("Record not found.")


def parse(raw):
    key, _, ident = str(raw or "").partition(":")
    if not key or not ident.isdigit():
        raise ValidationError({"target": "Choose a record."})
    return target_for(key), int(ident)


def resolve(user, raw):
    """Return (Target, object). Unknown and unreachable records are both 'not found', so existence never leaks."""
    target, pk = parse(raw)
    obj = target.model.objects.filter(pk=pk).first()
    if obj is None or not target.can_view(user, obj):
        raise NotFound("Record not found.")
    return target, obj


def content_type_for(obj):
    """Takes a record or a model class."""
    return ContentType.objects.get_for_model(obj if isinstance(obj, type) else obj.__class__)


def can_view_obj(user, obj):
    return target_for(target_key_for(obj)).can_view(user, obj)
