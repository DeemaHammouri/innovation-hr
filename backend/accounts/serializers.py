from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Department, Role, User, resolve_role
from .passwords import check_policy, generate_temporary_password


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


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "key", "department", "is_head", "name_en", "name_ar"]
        read_only_fields = fields


class UserWriteSerializer(serializers.ModelSerializer):
    """Create and edit a person. There is no password field: the server makes the temporary password and shows it once."""

    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    role = serializers.CharField(required=False)  # a role key such as "hr_member"; "head" / "member" still mean that seat in the department

    class Meta:
        model = User
        fields = ["full_name", "email", "username", "department", "role", "preferred_language"]

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

    def validate_username(self, value):
        value = (value or "").strip() or None
        if value is None:
            return None
        taken = User.objects.filter(username__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("Someone already uses this username.")
        return value

    def validate(self, attrs):
        department = attrs.get("department", getattr(self.instance, "department", None))
        wanted = attrs.pop("role", None)
        if wanted in (None, "head", "member"):
            current = getattr(self.instance, "role", "member") if wanted is None else wanted
            role_ref = resolve_role(department, current)
        else:
            role_ref = Role.objects.filter(key=wanted).first()
            # Roles come from the department's own list. Super Admin belongs to no department, so it can never be picked here.
            if role_ref is None or role_ref.department_id != department.pk:
                raise serializers.ValidationError({"role": "That role doesn't belong to this department."})
        if role_ref is None:
            raise serializers.ValidationError({"role": "Choose a role for this department."})
        if self.instance and self.instance.pk == self.context["request"].user.pk:
            if department != self.instance.department or role_ref != self.instance.role_ref:
                raise serializers.ValidationError({"role": "You can't change your own department or role."})
        attrs["role_ref"] = role_ref
        try:
            probe = User(pk=getattr(self.instance, "pk", None), department=department, role_ref=role_ref)
            probe.is_dept_head = bool(role_ref.is_head)
            probe.validate_placement()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    def create(self, validated_data):
        password = generate_temporary_password()
        user = User.objects.create_user(must_change_password=True, password=password, **validated_data)
        user.temporary_password = password  # handed to the view once; never stored in clear and never logged
        return user

    def update(self, instance, validated_data):
        # Only a seat that is in the payload AND different counts: a PATCH of the name alone must not sign the person out.
        moved = ("role_ref" in validated_data and validated_data["role_ref"] != instance.role_ref) or ("department" in validated_data and validated_data["department"] != instance.department)
        instance = super().update(instance, validated_data)
        if moved:
            instance.bump_token_version()  # a new seat means new rights: old tokens must not carry the old ones
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, required=False)
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.must_change_password:  # a deliberate change proves who is asking
            if not attrs.get("current_password") or not user.check_password(attrs["current_password"]):
                raise serializers.ValidationError({"current_password": "Your current password is not right."})
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "The two passwords don't match."})
        try:
            check_policy(user, attrs["new_password"])
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.detail})
        return attrs


class PreferredLanguageSerializer(serializers.ModelSerializer):
    """The only thing a signed-in user may change about themselves."""

    class Meta:
        model = User
        fields = ["preferred_language"]
