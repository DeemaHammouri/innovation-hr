import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Additive: the Capability and Role tables and the new user columns. Nothing existing is changed or removed."""

    dependencies = [("accounts", "0003_user_one_active_head_per_department")]

    operations = [
        migrations.CreateModel(
            name="Capability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=60, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=30, unique=True)),
                ("is_head", models.BooleanField(default=False)),
                ("name_en", models.CharField(max_length=80)),
                ("name_ar", models.CharField(max_length=80)),
                ("capabilities", models.ManyToManyField(blank=True, related_name="roles", to="accounts.capability")),
                ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="roles", to="accounts.department")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddField(model_name="user", name="role_ref", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="users", to="accounts.role")),
        migrations.AddField(model_name="user", name="is_dept_head", field=models.BooleanField(default=False, editable=False)),
        migrations.AddField(model_name="user", name="username", field=models.CharField(blank=True, max_length=150, null=True)),
        migrations.AddField(model_name="user", name="token_version", field=models.PositiveIntegerField(default=0)),
    ]
