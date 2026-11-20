"""Unit tests: notification audience targeting."""
from app.services.notifications import AudienceTarget, Recipient, filter_recipients, matches


def test_all_audience_matches_everyone():
    t = AudienceTarget("all", None, None, None)
    assert matches(t, Recipient("u1", "admin", None, None, None))
    assert matches(t, Recipient("u2", "teacher", None, None, None))
    assert matches(t, Recipient("u3", "student", "p", "c", "s"))


def test_role_audiences():
    assert matches(AudienceTarget("teachers", None, None, None), Recipient("u", "teacher", None, None, None))
    assert not matches(AudienceTarget("teachers", None, None, None), Recipient("u", "student", None, None, None))
    assert matches(AudienceTarget("admins", None, None, None), Recipient("u", "admin", None, None, None))
    assert matches(AudienceTarget("students", None, None, None), Recipient("u", "student", None, None, None))


def test_program_target():
    t = AudienceTarget("program", "p1", None, None)
    assert matches(t, Recipient("u", "student", "p1", "c", "s"))
    assert not matches(t, Recipient("u", "student", "p2", "c", "s"))
    assert not matches(t, Recipient("u", "teacher", "p1", None, None))


def test_class_target():
    t = AudienceTarget("class", None, "c1", None)
    assert matches(t, Recipient("u", "student", "p", "c1", "sA"))
    assert not matches(t, Recipient("u", "student", "p", "c2", "sA"))


def test_section_target_requires_class_and_section():
    t = AudienceTarget("section", None, "c1", "s1")
    assert matches(t, Recipient("u", "student", "p", "c1", "s1"))
    assert not matches(t, Recipient("u", "student", "p", "c1", "s2"))
    assert not matches(t, Recipient("u", "student", "p", "c2", "s1"))


def test_filter_recipients():
    t = AudienceTarget("section", None, "c1", "s1")
    recipients = [
        Recipient("u1", "student", "p", "c1", "s1"),
        Recipient("u2", "student", "p", "c1", "s2"),
        Recipient("u3", "teacher", None, None, None),
    ]
    assert [r.user_id for r in filter_recipients(t, recipients)] == ["u1"]
