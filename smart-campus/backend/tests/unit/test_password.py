"""Unit tests: password hashing & strength."""
import pytest

from app.security.password import (
    hash_password,
    is_strong_password,
    needs_rehash,
    verify_password,
)


def test_hash_and_verify():
    h = hash_password("Sup3rSecret!")
    assert h != "Sup3rSecret!"
    assert verify_password("Sup3rSecret!", h)
    assert not verify_password("wrong", h)


def test_hash_is_unique():
    assert hash_password("Sup3rSecret!") != hash_password("Sup3rSecret!")


def test_verify_empty_returns_false():
    assert verify_password("", "somehash") is False
    assert verify_password("x", "") is False


def test_hash_rejects_empty():
    with pytest.raises(ValueError):
        hash_password("")


def test_strength_checks():
    ok, _ = is_strong_password("Abcdefgh1!")
    assert ok
    weak_cases = ["short", "alllowercase1!", "ALLUPPER1!", "NoDigits!!", "NoSymbol1"]
    for pw in weak_cases:
        ok, reason = is_strong_password(pw)
        assert not ok, f"expected weak: {pw}"
        assert reason


def test_needs_rehash_returns_bool():
    h = hash_password("Sup3rSecret!")
    assert needs_rehash(h) in (True, False)
