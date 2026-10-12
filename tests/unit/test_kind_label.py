import pytest

from entries.templatetags.custom_filters import kind_label


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("EducationEntry", "Education"),
        ("OneLineEntry", "One line"),
        ("ReversedNumberedEntry", "Reversed numbered"),
        ("BulletEntry", "Bullet"),
        ("Entry", "Entry"),
    ],
)
def test_kind_label_from_class_name(raw, label):
    assert kind_label(raw) == label


def test_kind_label_from_an_instance():
    class PublicationEntry:  # the filter only reads the class name
        pass

    assert kind_label(PublicationEntry()) == "Publication"
