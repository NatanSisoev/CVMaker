"""SectionForm entry persistence.

Regression: ``save()`` used to call an overridden ``save_m2m`` that Django's
``save(commit=False)`` shadows with ``_save_m2m``, so checked entries were
silently dropped (caught by the Phase 4 e2e test).
"""

from __future__ import annotations

import pytest

from sections.forms import SectionForm
from sections.models import SectionEntry
from tests.factories import BulletEntryFactory, SectionFactory

pytestmark = pytest.mark.django_db


def _ordered(section):
    return list(section.section_entries.order_by("order").values_list("entry_id", flat=True))


def _form(user, entries, instance=None):
    return SectionForm(
        data={"title": "T", "alias": "t", "entries": [str(e.id) for e in entries]},
        user=user,
        instance=instance,
    )


def test_create_persists_checked_entries(user):
    a, b = BulletEntryFactory(user=user), BulletEntryFactory(user=user)
    form = _form(user, [a, b])
    assert form.is_valid(), form.errors

    section = form.save()

    assert section.user == user
    assert set(_ordered(section)) == {a.id, b.id}


def test_commit_false_then_save_m2m_also_persists(user):
    a = BulletEntryFactory(user=user)
    form = _form(user, [a])
    assert form.is_valid(), form.errors

    section = form.save(commit=False)
    section.save()
    form.save_m2m()

    assert _ordered(section) == [a.id]


def test_update_keeps_drag_order_appends_new_and_drops_unchecked(user):
    a, b, c, d = (BulletEntryFactory(user=user) for _ in range(4))
    section = SectionFactory(user=user)
    # Order as left by drag-reorder in the editor: c, a, b
    for order, entry in enumerate((c, a, b)):
        SectionEntry.objects.create(section=section, entry=entry, order=order)

    form = _form(user, [a, c, d], instance=section)  # b unchecked, d new
    assert form.is_valid(), form.errors
    form.save()

    assert _ordered(section) == [c.id, a.id, d.id]


def test_unchecking_everything_empties_the_section(user):
    a = BulletEntryFactory(user=user)
    section = SectionFactory(user=user)
    SectionEntry.objects.create(section=section, entry=a, order=0)

    form = _form(user, [], instance=section)
    assert form.is_valid(), form.errors
    form.save()

    assert _ordered(section) == []
