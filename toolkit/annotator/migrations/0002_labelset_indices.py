# Generated by Django 2.2.25 on 2022-01-06 02:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elastic', '0015_breakup_characters'),
        ('annotator', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='labelset',
            name='indices',
            field=models.ManyToManyField(to='elastic.Index'),
        ),
    ]
