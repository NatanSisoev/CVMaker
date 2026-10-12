import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from core.models import ContactMessage

pytestmark = pytest.mark.django_db
VALID = {"name": "Ada", "email": "ada@example.com", "message": "Hello there", "website": ""}


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()


def test_form_renders_and_prefills_for_signed_in_users(client, user):
    assert client.get(reverse("contact")).status_code == 200
    client.force_login(user)
    assert user.email in client.get(reverse("contact")).content.decode()


def test_message_is_stored_and_emailed_when_configured(client, settings):
    settings.CONTACT_EMAIL = "owner@example.com"
    resp = client.post(reverse("contact"), VALID)
    assert resp.status_code == 302
    assert ContactMessage.objects.get().message == "Hello there"
    assert [m.to for m in mail.outbox] == [["owner@example.com"]]


def test_stored_without_email_when_unconfigured(client, settings):
    settings.CONTACT_EMAIL = ""
    client.post(reverse("contact"), VALID)
    assert ContactMessage.objects.count() == 1 and not mail.outbox


def test_honeypot_silently_drops_bots(client, settings):
    settings.CONTACT_EMAIL = "owner@example.com"
    resp = client.post(reverse("contact"), {**VALID, "website": "http://spam"})
    assert resp.status_code == 302 and not ContactMessage.objects.exists() and not mail.outbox


def test_invalid_input_rerenders(client):
    resp = client.post(reverse("contact"), {**VALID, "email": "nope"})
    assert resp.status_code == 200 and not ContactMessage.objects.exists()


def test_rate_limited_per_ip(client):
    for _ in range(5):
        assert client.post(reverse("contact"), VALID).status_code == 302
    assert client.post(reverse("contact"), VALID).status_code == 429
