from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

ADMINISTRATION = "Administration"
MARKETING = "Marketing"
OPERATION = "Operation"
DEPARTMENT_NAMES = [ADMINISTRATION, MARKETING, "Commercial", "HR", OPERATION]


class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
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
    class Role(models.TextChoices):
        HEAD = "head", "Head"
        MEMBER = "member", "Member"

    class Language(models.TextChoices):
        EN = "en", "English"
        AR = "ar", "Arabic"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    # Empty only for developer superusers made with `createsuperuser`.
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="users", null=True, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
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
            models.UniqueConstraint(fields=["department"], condition=models.Q(role="head", is_active=True, department__isnull=False), name="one_active_head_per_department"),
        ]

    def __str__(self):
        return self.email

    @property
    def is_ceo(self):
        return bool(self.department_id and self.department.name == ADMINISTRATION and self.role == self.Role.HEAD)

    @property
    def is_operation_head(self):
        return bool(self.department_id and self.department.name == OPERATION and self.role == self.Role.HEAD)

    @property
    def can_manage_clients(self):
        return self.is_ceo or self.is_operation_head

    def validate_placement(self):
        """Department rules. Counts every user, active or not, so a seat is never double-booked."""
        if not self.department_id:
            return
        others = User.objects.filter(department_id=self.department_id).exclude(pk=self.pk)
        name = self.department.name
        if name == ADMINISTRATION:
            if self.role != self.Role.HEAD:
                raise ValidationError({"role": "Administration only has the CEO, who is its head."})
            if others.exists():
                raise ValidationError({"department": "Administration already has its CEO."})
        elif name == MARKETING:
            if others.exists():
                raise ValidationError({"department": "Marketing already has its one person."})
        elif self.role == self.Role.HEAD and others.filter(role=self.Role.HEAD).exists():
            raise ValidationError({"role": f"{name} already has a head. Change their role first."})

    def save(self, *args, **kwargs):
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
