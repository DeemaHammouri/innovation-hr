from django.db import migrations, models


class Migration(migrations.Migration):
    """Drops the old head/member column. Applied only after the whole suite passed without code reading it.
    Reversing re-adds the column (default member); reversing 0005 then rewrites it from role_ref."""

    dependencies = [("accounts", "0006_head_constraint_username")]
    operations = [migrations.RemoveField(model_name="user", name="role")]
