"""Transactional email (Phase 6): provider selection, branded allauth mails,
welcome email, opt-in render notifications."""

from __future__ import annotations

import re

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.urls import reverse

from cv.models import CVInfo
from rendering import services as rendering_services
from rendering import tasks
from rendering.models import RenderStatus
from rendering.services import enqueue_render
from sections.models import CVSection, SectionEntry
from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

pytestmark = pytest.mark.django_db
PASSWORD = "pbkdf2-dev-only-password"


def _html(message) -> str:
    (alternative,) = [body for body, mime in message.alternatives if mime == "text/html"]
    return alternative


def _signup(client, email="new@example.com"):
    client.post(
        reverse("account_signup"), {"email": email, "password1": PASSWORD, "password2": PASSWORD}
    )


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("provider", "backend"),
    [
        ("console", "django.core.mail.backends.console.EmailBackend"),
        ("smtp", "django.core.mail.backends.smtp.EmailBackend"),
        ("resend", "anymail.backends.resend.EmailBackend"),
        ("postmark", "anymail.backends.postmark.EmailBackend"),
    ],
)
def test_email_provider_selects_backend(monkeypatch, provider, backend):
    import importlib

    import cvmaker.settings.base as base

    monkeypatch.setenv("EMAIL_PROVIDER", provider)
    # Empty (not deleted): reload re-reads .env, which may set the escape hatch.
    monkeypatch.setenv("DJANGO_EMAIL_BACKEND", "")
    try:
        assert backend == importlib.reload(base).EMAIL_BACKEND
    finally:
        monkeypatch.delenv("EMAIL_PROVIDER")
        importlib.reload(base)


def test_unknown_email_provider_fails_loudly(monkeypatch):
    import importlib

    from django.core.exceptions import ImproperlyConfigured

    import cvmaker.settings.base as base

    monkeypatch.setenv("EMAIL_PROVIDER", "carrier-pigeon")
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(base)
    monkeypatch.delenv("EMAIL_PROVIDER")
    importlib.reload(base)


# ---------------------------------------------------------------------------
# allauth emails, branded
# ---------------------------------------------------------------------------
def test_signup_confirmation_is_branded_multipart(client):
    _signup(client)
    (message,) = mail.outbox

    assert message.subject == "[CVMaker] Confirm your email to start using CVMaker"
    assert "Hello from" not in message.body  # allauth's host-based greeting replaced
    link = re.search(r"https?://\S+", message.body).group(0)
    html = _html(message)
    assert "Confirm email" in html and link in html
    assert html.lstrip().startswith("<!DOCTYPE html>")


def test_password_reset_email_is_branded_multipart(client, user):
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    client.post(reverse("account_reset_password"), {"email": user.email})
    (message,) = mail.outbox
    assert message.subject == "[CVMaker] Reset your CVMaker password"
    assert "Choose a new password" in _html(message)


# ---------------------------------------------------------------------------
# Welcome
# ---------------------------------------------------------------------------
def test_welcome_is_sent_once_after_the_first_confirmation(client):
    _signup(client)
    confirm = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
    client.post(confirm)

    welcome = [m for m in mail.outbox if "Welcome to CVMaker" in m.subject]
    assert len(welcome) == 1
    assert welcome[0].to == ["new@example.com"]
    assert "/cv/" in _html(welcome[0])

    # Confirming a second address later (through allauth's email page, as a
    # signed-in user would) doesn't welcome again.
    mail.outbox.clear()
    client.post(reverse("account_email"), {"email": "second@example.com", "action_add": ""})
    second_link = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
    client.post(second_link)
    assert EmailAddress.objects.get(email="second@example.com").verified
    assert not [m for m in mail.outbox if "Welcome to CVMaker" in m.subject]


# ---------------------------------------------------------------------------
# Render notifications (opt-in)
# ---------------------------------------------------------------------------
@pytest.fixture
def renderable_cv(user):
    info = CVInfo.objects.create(user=user, alias="me", name="Ada")
    cv = CVFactory(user=user, alias="notify-cv", info=info)
    section = SectionFactory(user=user, title="Highlights")
    SectionEntry.objects.create(section=section, entry=BulletEntryFactory(user=user), order=0)
    CVSection.objects.create(cv=cv, section=section, order=0)
    return cv


@pytest.fixture
def no_dispatch(monkeypatch):
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda render: None)


def test_no_email_unless_opted_in(user, renderable_cv, no_dispatch):
    render = enqueue_render(renderable_cv, requested_by=user)
    tasks.render_cv(render.id)
    assert mail.outbox == []


def test_done_email_links_pdf_and_editor(user, renderable_cv, no_dispatch, settings):
    settings.SITE_URL = "https://cvmaker.example"
    user.notify_on_render = True
    user.save()

    render = enqueue_render(renderable_cv, requested_by=user)
    tasks.render_cv(render.id)

    (message,) = mail.outbox
    assert message.subject == '[CVMaker] Your CV "notify-cv" is ready'
    assert f"https://cvmaker.example/renders/{render.id}/pdf/" in message.body
    assert f"https://cvmaker.example/cv/{renderable_cv.id}/editor/" in _html(message)


def test_failed_email_carries_the_error(user, renderable_cv, no_dispatch, monkeypatch):
    user.notify_on_render = True
    user.save()

    def boom(payload, style=""):
        raise tasks._RenderError("Theme 'nope' does not exist.")

    monkeypatch.setattr(tasks, "_render_payload_to_pdf", boom)
    render = enqueue_render(renderable_cv, requested_by=user)
    tasks.render_cv(render.id)

    (message,) = mail.outbox
    assert message.subject == '[CVMaker] Rendering "notify-cv" failed'
    assert "Theme &#x27;nope&#x27; does not exist." in _html(message)  # escaped in HTML
    assert "Theme 'nope' does not exist." in message.body


def test_email_failure_never_fails_the_render(user, renderable_cv, no_dispatch, monkeypatch):
    user.notify_on_render = True
    user.save()

    def broken_send(*args, **kwargs):
        raise ConnectionError("SMTP down")

    monkeypatch.setattr("core.email.EmailMultiAlternatives.send", broken_send)
    render = enqueue_render(renderable_cv, requested_by=user)
    tasks.render_cv(render.id)

    render.refresh_from_db()
    assert render.status == RenderStatus.DONE


def test_settings_toggle_saves(client, user):
    client.force_login(user)
    client.post(
        reverse("profile"),
        {
            "action": "profile",
            "display_name": "",
            "preferred_language": "en",
            "notify_on_render": "on",
        },
    )
    user.refresh_from_db()
    assert user.notify_on_render is True
