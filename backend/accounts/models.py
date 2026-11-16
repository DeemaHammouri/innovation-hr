from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .catalog import ADMINISTRATION, DEPARTMENT_NAMES, MARKETING, OPERATION, ROLES, SUPER_ADMIN  # noqa: F401


class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Capability(models.Model):
    """One thing a person may do ("quotation.sign"). Views ask for capabilities, never for role names."""

    code = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Role(models.Model):
    """A job in the company. Belongs to a department (Super Admin to none) and holds capabilities."""

    key = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="roles", null=True, blank=True)
    is_head = models.BooleanField(default=False)
    name_en = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80)
    capabilities = models.ManyToManyField(Capability, related_name="roles", blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.key


def resolve_role(department, legacy_role=None, superuser=False):
    """The Role for a department seat. Seeds the organisation on first use so a fresh database works."""
    from .organization import ensure_organization

    roles = ensure_organization()
    if superuser and department is None:
        return roles[SUPER_ADMIN]
    if department is None:
        return None
    wanted_head = legacy_role == "head"
    for role in roles.values():
        if role.department_id == department.pk and (role.is_head == wanted_head or department.name == MARKETING):
            return role
    return None


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        legacy = extra.pop("role", None)  # "head" or "member": a convenience that picks the Role for the department
        if "role_ref" not in extra and "role_ref_id" not in extra:
            extra["role_ref"] = resolve_role(extra.get("department"), legacy, extra.get("is_superuser", False))
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save()
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        # Django admin superuser, for developers only. Has no department.
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Language(models.TextChoices):
        EN = "en", "English"
        AR = "ar", "Arabic"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    # Empty only for developer superusers made with `createsuperuser`.
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="users", null=True, blank=True)
    role_ref = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users", null=True, blank=True)
    # Mirrors role_ref.is_head so the database itself can enforce one head per department.
    is_dept_head = models.BooleanField(default=False, editable=False)
    username = models.CharField(max_length=150, null=True, blank=True)
    token_version = models.PositiveIntegerField(default=0)
    must_change_password = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=2, choices=Language.choices, default=Language.EN)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]
    objects = UserManager()

    class Meta:
        ordering = ["full_name"]
        constraints = [
            # A department has at most one active head, enforced by the database as well as by the user screens.
            models.UniqueConstraint(fields=["department"], condition=models.Q(is_dept_head=True, is_active=True, department__isnull=False), name="one_active_head_per_department"),
            models.UniqueConstraint(Lower("username"), condition=models.Q(username__isnull=False), name="unique_username_ci"),
        ]

    def __str__(self):
        return self.email

    @property
    def role(self):
        """"head" or "member" within the department (read-only; change role_ref instead)."""
        return "head" if self.role_ref_id and self.role_ref.is_head else "member"

    @property
    def role_name(self):
        return self.role_ref.key if self.role_ref_id else None

    @property
    def is_super_admin(self):
        return self.role_name == SUPER_ADMIN

    @property
    def capability_codes(self):
        """The set of capability codes this person holds, read once per user object."""
        if not self.is_active or not self.role_ref_id:
            return frozenset()
        cached = self.__dict__.get("_caps")
        if cached is None:
            cached = self.__dict__["_caps"] = frozenset(Capability.objects.filter(roles=self.role_ref_id).values_list("code", flat=True))  # one query
        return cached

    def bump_token_version(self):
        """Every token issued so far stops working (password change, reset, deactivation, role change)."""
        User.objects.filter(pk=self.pk).update(token_version=models.F("token_version") + 1)
        self.token_version = User.objects.values_list("token_version", flat=True).get(pk=self.pk)

    def has_capability(self, code):
        return code in self.capability_codes

    def refresh_from_db(self, *args, **kwargs):
        self.__dict__.pop("_caps", None)
        super().refresh_from_db(*args, **kwargs)

    def validate_placement(self):
        """Department rules. Counts every user, active or not, so a seat is never double-booked."""
        if not self.department_id:
            return
        others = User.objects.filter(department_id=self.department_id).exclude(pk=self.pk)
        name = self.department.name
        if name == ADMINISTRATION:
            if not self.is_dept_head:
                raise ValidationError({"role": "Administration only has the CEO, who is its head."})
            if others.exists():
                raise ValidationError({"department": "Administration already has its CEO."})
        elif name == MARKETING:
            if others.exists():
                raise ValidationError({"department": "Marketing already has its one person."})
        elif self.is_dept_head and others.filter(is_dept_head=True).exists():
            raise ValidationError({"role": f"{name} already has a head. Change their role first."})

    def save(self, *args, **kwargs):
        if self.role_ref_id is None and (self.department_id or self.is_superuser):
            self.role_ref = resolve_role(self.department, None, self.is_superuser)
        self.is_dept_head = bool(self.role_ref_id and self.role_ref.is_head and self.department_id)
        self.__dict__.pop("_caps", None)
        self.validate_placement()  # enforced here so no code path can skip the rules
        super().save(*args, **kwargs)


class ActionLog(models.Model):
    """One row per login or logout. Indexed by user and time, ready for attendance reports."""

    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="action_logs")
    action = models.CharField(max_length=20, choices=Action.choices)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.action} {self.timestamp:%Y-%m-%d %H:%M}"
