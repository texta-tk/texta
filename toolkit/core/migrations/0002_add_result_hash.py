from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='result_hash',
            field=models.CharField(default='', max_length=100),
        ),
    ]
