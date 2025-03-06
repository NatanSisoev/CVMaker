# Generated by Django 5.1.6 on 2025-03-06 09:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cv', '0001_initial'),
        ('sections', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='cv',
            name='sections',
            field=models.ManyToManyField(blank=True, related_name='cvs', through='sections.CVSection', to='sections.section'),
        ),
        migrations.AddField(
            model_name='cv',
            name='user',
            field=models.ForeignKey(default=1, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cvs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cvdesign',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cv_designs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cv',
            name='design',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cv.cvdesign'),
        ),
        migrations.AddField(
            model_name='cvinfo',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cv_info', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cv',
            name='info',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cv.cvinfo'),
        ),
        migrations.AddField(
            model_name='cvlocale',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cv_locales', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cv',
            name='locale',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cv.cvlocale'),
        ),
        migrations.AddField(
            model_name='cvsettings',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cv_settings', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='cv',
            name='settings',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cv.cvsettings'),
        ),
    ]
