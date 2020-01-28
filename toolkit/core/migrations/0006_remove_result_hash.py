
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_remove_project_owner'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='task',
            name='result_hash',
        ),
    ]
