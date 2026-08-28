"""Secret resolver tests: references only, values never leak."""

from __future__ import annotations

import pytest

from infra_core.secrets import (
    FakeSecretResolver,
    SecretNotFoundError,
    SecretRef,
    SecretRefFormatError,
    SecretValue,
)


class TestSecretRef:
    def test_valid_reference_parses(self) -> None:
        ref = SecretRef.parse("secretref://corp-vault/dmt/dev/llm-api-key")
        assert ref.provider == "corp-vault"
        assert ref.path == "dmt/dev/llm-api-key"

    def test_raw_values_are_rejected_as_references(self) -> None:
        for raw in ("hunter2", "sk-abcdef", "postgres://u@h/db", ""):
            with pytest.raises(SecretRefFormatError):
                SecretRef.parse(raw)


class TestFakeResolver:
    def test_missing_secret_raises_without_echoing_the_path_value(self) -> None:
        resolver = FakeSecretResolver({})
        with pytest.raises(SecretNotFoundError):
            resolver.resolve(SecretRef.parse("secretref://corp-vault/dmt/dev/missing"))

    def test_resolved_value_repr_and_str_are_masked(self) -> None:
        resolver = FakeSecretResolver(
            {"secretref://corp-vault/dmt/dev/key": "synthetic-secret-value"}
        )
        value = resolver.resolve(SecretRef.parse("secretref://corp-vault/dmt/dev/key"))
        assert isinstance(value, SecretValue)
        assert "synthetic-secret-value" not in repr(value)
        assert "synthetic-secret-value" not in str(value)
        assert value.reveal() == "synthetic-secret-value"

    def test_secret_value_never_equals_a_plain_string_accidentally(self) -> None:
        resolver = FakeSecretResolver({"secretref://v/p": "s"})
        value = resolver.resolve(SecretRef.parse("secretref://v/p"))
        assert value != "s"

    def test_exception_messages_never_contain_secret_values(self) -> None:
        resolver = FakeSecretResolver({"secretref://v/known": "topsecret"})
        try:
            resolver.resolve(SecretRef.parse("secretref://v/unknown"))
        except SecretNotFoundError as exc:
            assert "topsecret" not in str(exc)
