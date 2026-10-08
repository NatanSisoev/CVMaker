"""``manage.py seed_demo`` -- a ready-to-explore account for local testing.

Creates demo@cvmaker.test (verified, password printed) with a CV in English
that has Spanish and French translations, so the editor, language chips,
side-by-side translation editing, drag-reorder and rendering all have
something to show. Idempotent: running it again resets the demo account.
"""

from __future__ import annotations

import datetime

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.gdpr import delete_account
from cv.models import CV, CVDesign, CVInfo
from entries.models import (
    BulletEntry,
    EducationEntry,
    ExperienceEntry,
    OneLineEntry,
    PublicationEntry,
)
from sections.models import CVSection, Section, SectionEntry

EMAIL = "demo@cvmaker.test"
PASSWORD = "demo-password-123"
D = datetime.date


class Command(BaseCommand):
    help = "Create (or reset) the demo account with a translated, renderable CV."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        existing = User.objects.filter(email=EMAIL).first()
        if existing:
            delete_account(existing)
            self.stdout.write("Reset the existing demo account.")

        user = User.objects.create_user(
            username="demo", email=EMAIL, password=PASSWORD, display_name="Ada Demo"
        )
        EmailAddress.objects.create(user=user, email=EMAIL, verified=True, primary=True)

        info = CVInfo.objects.create(
            user=user,
            alias="ada",
            name="Ada Lovelace",
            location="London, UK",
            email="ada@example.com",
            website="https://example.com/ada",
            social_networks={"GitHub": "ada-demo"},
        )
        design = CVDesign.objects.create(user=user, alias="classic", theme="classic")

        experience = [
            ExperienceEntry.objects.create(
                user=user,
                alias="analytical-engine",
                company="Analytical Engine Company",
                position="Mathematician and Programmer",
                location="London",
                start_date=D(1842, 9, 1),
                end_date=D(1843, 10, 1),
                summary="Wrote the first published computer program.",
                highlights="Algorithm for Bernoulli numbers; Foresaw general-purpose computing",
                translations={
                    "es": {
                        "position": "Matem\u00e1tica y programadora",
                        "summary": "Escribi\u00f3 el primer programa de ordenador publicado.",
                        "highlights": "Algoritmo para los n\u00fameros de Bernoulli; Anticip\u00f3 la computaci\u00f3n de prop\u00f3sito general",
                    },
                    "fr": {"position": "Math\u00e9maticienne et programmeuse"},
                },
            ),
            ExperienceEntry.objects.create(
                user=user,
                alias="royal-society",
                company="Royal Society salons",
                position="Correspondent",
                start_date=D(1835, 1, 1),
                end_date=D(1842, 8, 1),
                highlights="Corresponded with Faraday and Babbage",
                translations={"es": {"position": "Corresponsal"}},
            ),
        ]
        education = [
            EducationEntry.objects.create(
                user=user,
                alias="private-tutors",
                institution="Private tutors",
                area="Mathematics",
                degree="Self-directed",
                start_date=D(1828, 1, 1),
                end_date=D(1835, 1, 1),
                translations={"es": {"area": "Matem\u00e1ticas", "degree": "Autodidacta"}},
            )
        ]
        publications = [
            PublicationEntry.objects.create(
                user=user,
                alias="notes-on-the-engine",
                title="Notes on the Analytical Engine",
                authors="Ada Lovelace, Luigi Menabrea",
                journal="Scientific Memoirs",
                date=D(1843, 10, 1),
                translations={"es": {"title": "Notas sobre la M\u00e1quina Anal\u00edtica"}},
            )
        ]
        skills = [
            OneLineEntry.objects.create(
                user=user,
                alias="languages",
                label="Languages",
                details="English, French, Italian",
                translations={
                    "es": {"label": "Idiomas", "details": "Ingl\u00e9s, franc\u00e9s, italiano"}
                },
            ),
            OneLineEntry.objects.create(
                user=user, alias="methods", label="Methods", details="Analysis, notation"
            ),
        ]
        BulletEntry.objects.create(
            user=user, alias="unused-bullet", bullet="An entry that is in no section yet"
        )

        cv = CV.objects.create(user=user, alias="ada-cv", info=info, design=design)
        for order, (title, entries) in enumerate(
            (
                ("Experience", experience),
                ("Education", education),
                ("Publications", publications),
                ("Skills", skills),
            )
        ):
            section = Section.objects.create(user=user, title=title, alias=title.lower())
            for entry_order, entry in enumerate(entries):
                SectionEntry.objects.create(section=section, entry=entry, order=entry_order)
            CVSection.objects.create(cv=cv, section=section, order=order)

        self.stdout.write(self.style.SUCCESS("Demo account ready."))
        self.stdout.write(f"  email:    {EMAIL}")
        self.stdout.write(f"  password: {PASSWORD}")
        self.stdout.write(f"  CV:       {cv.alias} ({cv.id})")
