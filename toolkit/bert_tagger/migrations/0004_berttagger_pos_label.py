# Generated by Django 2.2.19 on 2021-07-07 14:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bert_tagger', '0003_auto_20210617_1739'),
    ]

    operations = [
        migrations.AddField(
            model_name='berttagger',
            name='pos_label',
            field=models.CharField(blank=True, default='', max_length=1000, null=True),
        ),
    ]
