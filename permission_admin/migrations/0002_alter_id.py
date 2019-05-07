from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permission_admin', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scriptproject',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
