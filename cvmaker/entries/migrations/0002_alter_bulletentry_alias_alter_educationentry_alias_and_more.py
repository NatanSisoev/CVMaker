# Generated by Django 5.1.6 on 2025-03-01 22:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bulletentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='educationentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='experienceentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='normalentry',
            name='alias',
            field=models.CharField(default='tmp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='numberedentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='onelineentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='publicationentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='reversednumberedentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='textentry',
            name='alias',
            field=models.CharField(default='temp', help_text='Alias for the CV entry', max_length=20),
            preserve_default=False,
        ),
    ]
