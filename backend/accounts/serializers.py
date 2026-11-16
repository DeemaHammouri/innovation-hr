from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import resolve_role, Department, User

MIN_PASSWORD_LENGTH = 8


def check_password_length(value):
    if len(value) < MIN_PASSWORD_LENGTH:
        raise serializers.ValidationError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    return value


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    """What the API returns about a user."""

    department_name = serializers.CharField(source="department.name", default=None, read_only=True)
    permissions = serializers.SerializerMethodField()
    role_key = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "full_name", "email", "username", "department", "department_name", "role", "role_key", "capabilities",
            "is_active", "must_change_password", "preferred_language", "permissions",
        ]
        read_only_fields = fields

    def get_role_key(self, user):
        from core.roles import role_key

        return role_key(user)

    def get_capabilities(self, user):
        return sorted(user.capability_codes)

    def get_permissions(self, user):
        # The frontend uses these only to decide what to show. The backend enforces them again.
        return {"manage_users": user.has_capability("user.manage"), "manage_clients": user.has_capability("client.manage")}


class UserWriteSerializer(serializers.ModelSerializer):
    temporary_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    role = serializers.ChoiceField(choices=["head", "member"], required=False)  # replaced by explicit roles in objective 5

    class Meta:
        model = User
        fields = ["full_name", "email", "department", "role", "preferred_language", "temporary_password"]

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the person's full name.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        taken = User.objects.filter(email__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("Someone already uses this email.")
        return value

    def validate_temporary_password(self, value):
        return check_password_length(value)

    def validate(self, attrs):
        if self.instance is None and not attrs.get("temporary_password"):
            raise serializers.ValidationError({"temporary_password": "Add a temporary password."})
        department = attrs.get("department", getattr(self.instance, "department", None))
        role = attrs.pop("role", getattr(self.instance, "role", "member"))
        role_ref = resolve_role(department, role)
        if self.instance and self.instance.pk == self.context["request"].user.pk:
            if department != self.instance.department or role_ref != self.instance.role_ref:
                raise serializers.ValidationError(
                    {"role": "You can't change your own department or role."}
                )
        attrs["role_ref"] = role_ref
        try:
            probe = User(pk=getattr(self.instance, "pk", None), department=department, role_ref=role_ref)
            probe.is_dept_head = bool(role_ref and role_ref.is_head)
            probe.validate_placement()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("temporary_password")
        return User.objects.create_user(must_change_password=True, password=password, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("temporary_password", None)  # passwords change through "Reset password"
        return super().update(instance, validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        check_password_length(value)
        if self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Choose a password that's different from the temporary one.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "The two passwords don't match."})
        return attrs


class PreferredLanguageSerializer(serializers.ModelSerializer):
    """The only thing a signed-in user may change about themselves."""

    class Meta:
        model = User
        fields = ["preferred_language"]
