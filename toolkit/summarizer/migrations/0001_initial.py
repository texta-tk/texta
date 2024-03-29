# Generated by Django 2.2.20 on 2021-04-30 11:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0014_userprofile_application'),
        ('elastic', '0008_indexsplitter_str_val'),
    ]

    operations = [
        migrations.CreateModel(
            name='Summarizer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=1000)),
                ('query', models.TextField(default='{"query": {"match_all": {}}}')),
                ('fields', models.TextField(default='[]')),
                ('algorithm', models.TextField(default='[]')),
                ('ratio', models.DecimalField(decimal_places=1, max_digits=2)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('indices', models.ManyToManyField(to='elastic.Index')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Project')),
                ('task', models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.Task')),
            ],
        ),
    ]
