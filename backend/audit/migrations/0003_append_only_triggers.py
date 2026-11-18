from django.db import migrations

from audit import triggers


def create(apps, schema_editor):
    triggers.create(schema_editor)


def drop(apps, schema_editor):
    triggers.drop(schema_editor)


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_security_event")]
    operations = [migrations.RunPython(create, drop)]
