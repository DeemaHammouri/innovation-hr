from django.db import transaction
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from audit.models import record
from core import access
from core.redact import RedactFreeText
from core.pagination import StandardPagination
from notifications.service import notify

from .models import Comment


class CommentSerializer(RedactFreeText, serializers.ModelSerializer):
    redacted_fields = ("body",)
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    mentions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "author_name", "body", "mentions", "created_at"]
        read_only_fields = fields


def mentionable_users(user, obj):
    """Active people who can open this record. Mentions are limited to them, so a mention never leaks a record."""
    return [u for u in User.objects.filter(is_active=True, is_superuser=False).select_related("department") if access.can_view_obj(u, obj)]


class CommentListCreateView(ListCreateAPIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    """GET or POST /api/comments/?target=client:5"""

    serializer_class = CommentSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        _, obj = access.resolve(self.request.user, self.request.query_params.get("target"))
        return Comment.objects.filter(content_type=access.content_type_for(obj), object_id=obj.pk).select_related("author").prefetch_related("mentions")

    def create(self, request, *args, **kwargs):
        target, obj = access.resolve(request.user, request.query_params.get("target") or request.data.get("target"))
        if not target.may_comment(request.user, obj):
            raise PermissionDenied("You can't comment on this record.")
        body = str(request.data.get("body", "")).strip()
        if not body:
            raise serializers.ValidationError({"body": "Write a comment first."})
        if len(body) > 4000:
            raise serializers.ValidationError({"body": "Keep the comment under 4000 characters."})
        wanted = request.data.get("mentions") or []
        if not isinstance(wanted, list) or not all(isinstance(i, int) for i in wanted):
            raise serializers.ValidationError({"mentions": "Choose people from the list."})
        allowed = {u.pk: u for u in mentionable_users(request.user, obj)}
        if any(i not in allowed for i in wanted):
            raise serializers.ValidationError({"mentions": "You can only mention people who can open this record."})

        with transaction.atomic():
            comment = Comment.objects.create(author=request.user, content_type=access.content_type_for(obj), object_id=obj.pk, body=body)
            comment.mentions.set([allowed[i] for i in set(wanted)])
            record(request.user, obj, "commented", comment=body[:200])
        label = target.label(obj) if target.label else ""
        link = target.link(obj) if target.link else ""
        for person in comment.mentions.all():
            if person.pk != request.user.pk:
                notify(person, "mention", link=link, actor=request.user.full_name, ref=label, name=body[:120])
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class MentionableView(APIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    """GET /api/mentionable/?target=client:5 : who can be @mentioned on this record."""

    def get(self, request):
        _, obj = access.resolve(request.user, request.query_params.get("target"))
        people = [{"id": u.pk, "full_name": u.full_name} for u in mentionable_users(request.user, obj) if u.pk != request.user.pk]
        return Response(people)
