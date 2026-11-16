from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("operations", "0007_backfill_task_periods")]
    operations = [migrations.AlterField(model_name="taskinstance", name="period", field=models.DateField())]
