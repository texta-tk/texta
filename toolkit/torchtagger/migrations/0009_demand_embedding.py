# Generated by Django 2.2.28 on 2022-05-20 12:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('torchtagger', '0008_torchtagger_pos_label'),
    ]

    operations = [
        migrations.AlterField(
            model_name='torchtagger',
            name='embedding',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='embedding.Embedding'),
        ),
    ]
