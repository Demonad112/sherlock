import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sherlock_console import (  # noqa: E402
    email_candidates, name_candidates, normalize_phone_ca, phone_candidates,
    username_candidates,
)


@pytest.mark.parametrize("raw,e164", [
    ("(403) 555-0123", "+14035550123"),
    ("+1 780 555 0123", "+17805550123"),
    ("1-587-555-0123", "+15875550123"),
    ("825.555.0123", "+18255550123"),
])
def test_phone_valid(raw, e164):
    assert normalize_phone_ca(raw)["e164"] == e164


@pytest.mark.parametrize("raw", ["123", "", "0035550123", "4030550123", "911-555-0123", None])
def test_phone_invalid(raw):
    assert normalize_phone_ca(raw) is None


def test_phone_alberta_flag():
    assert normalize_phone_ca("403-555-0123")["alberta"]
    assert not normalize_phone_ca("416-555-0123")["alberta"]


def test_phone_candidates():
    c = [x for x, _ in phone_candidates("(403) 555-0123")]
    assert "4035550123" in c and "403-555-0123" in c
    with pytest.raises(ValueError):
        phone_candidates("nope")


def test_email_candidates():
    c = [x for x, _ in email_candidates("Jane.Doe+news@gmail.com")]
    assert c[0] == "jane.doe+news"
    assert {"jane.doe", "janedoe", "jane_doe", "jane-doe"} <= set(c)
    assert len(c) == len(set(c))
    with pytest.raises(ValueError):
        email_candidates("not-an-email")


def test_name_candidates():
    c = [x for x, _ in name_candidates("Jane Q. Doe")]
    assert {"janedoe", "jane.doe", "jdoe", "janed", "doejane"} <= set(c)
    assert len(name_candidates("Jane Doe", max_variants=3)) == 3
    with pytest.raises(ValueError):
        name_candidates("Madonna")


def test_username_expansion():
    assert [x for x, _ in username_candidates("a{?}b")] == ["a_b", "a-b", "a.b"]
    assert username_candidates("abc") == [("abc", "direct")]
