"""factory-boy factories for CVMaker domain objects.

Kept in one file for now because the model count is manageable. If the file
grows past ~400 lines, split per-app (`tests/factories/accounts.py`, etc.).

Every factory:
  - accepts explicit kwargs that override any default
  - owns a sensible `alias` value so list-and-filter queries in tests aren't
    polluted by duplicate aliases
  - uses `factory.Faker` for locale-dependent strings so tests read naturally

The import paths below are short (`accounts`, `cv`, `entries`, `sections`)
because `apps/` is on `sys.path` per `settings.base`. If you move/rename apps,
update here too.
"""

from __future__ import annotations

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    display_name = factory.Faker("name")
    preferred_language = "en"
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "pbkdf2-testing-only")
        user = model_class(*args, **kwargs)
        user.set_password(password)
        user.save()
        return user


# ---------------------------------------------------------------------------
# cv
# ---------------------------------------------------------------------------
class CVFactory(DjangoModelFactory):
    class Meta:
        model = "cv.CV"

    user = factory.SubFactory(UserFactory)
    alias = factory.Sequence(lambda n: f"cv-{n}")


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
class SectionFactory(DjangoModelFactory):
    class Meta:
        model = "sections.Section"

    user = factory.SubFactory(UserFactory)
    title = factory.Faker("sentence", nb_words=3)
    alias = factory.Sequence(lambda n: f"section-{n}")


# ---------------------------------------------------------------------------
# entries
# ---------------------------------------------------------------------------
class _BaseEntryFactoryMixin:
    """Shared defaults for every entry factory."""

    user = factory.SubFactory(UserFactory)
    alias = factory.Sequence(lambda n: f"entry-{n}")


class EducationEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.EducationEntry"

    institution = factory.Faker("company")
    area = factory.Faker("job")
    degree = "BS"
    location = factory.Faker("city")


class ExperienceEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.ExperienceEntry"

    company = factory.Faker("company")
    position = factory.Faker("job")
    location = factory.Faker("city")


class NormalEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.NormalEntry"

    name = factory.Faker("catch_phrase")


class PublicationEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.PublicationEntry"

    title = factory.Faker("sentence", nb_words=6)
    authors = factory.Faker("name")


class OneLineEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.OneLineEntry"

    label = factory.Faker("word")
    details = factory.Faker("sentence")


class BulletEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.BulletEntry"

    bullet = factory.Faker("sentence")


class NumberedEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.NumberedEntry"

    number = factory.Faker("sentence")


class ReversedNumberedEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.ReversedNumberedEntry"

    reversed_number = factory.Faker("sentence")


class TextEntryFactory(_BaseEntryFactoryMixin, DjangoModelFactory):
    class Meta:
        model = "entries.TextEntry"

    text = factory.Faker("paragraph")
