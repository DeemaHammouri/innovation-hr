from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    """One head per department now rests on is_dept_head; usernames are unique ignoring case."""

    dependencies = [("accounts", "0005_backfill_roles")]

    operations = [
        migrations.RemoveConstraint(model_name="user", name="one_active_head_per_department"),
        migrations.AddConstraint(model_name="user", constraint=models.UniqueConstraint(condition=models.Q(("department__isnull", False), ("is_active", True), ("is_dept_head", True)), fields=("department",), name="one_active_head_per_department")),
        migrations.AddConstraint(model_name="user", constraint=models.UniqueConstraint(Lower("username"), condition=models.Q(("username__isnull", False)), name="unique_username_ci")),
    ]
