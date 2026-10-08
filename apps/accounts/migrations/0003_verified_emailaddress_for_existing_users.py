"""Give every pre-allauth user a verified, primary allauth EmailAddress.

With ACCOUNT_EMAIL_VERIFICATION = "mandatory", a user without one would be
sent through verification on their next login. Their address was already
the login identifier, so it is treated as verified.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.exclude(email="").iterator():
        if not EmailAddress.objects.filter(user=user).exists():
            EmailAddress.objects.create(
                user=user, email=user.email.lower(), verified=True, primary=True
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_waitlistentry"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
