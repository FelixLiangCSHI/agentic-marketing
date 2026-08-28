"""Object store tests: prefixes, hashing, versioning, no in-place overwrite."""

from __future__ import annotations

import hashlib

import pytest

from infra_core.objectstore import (
    FakeObjectStore,
    MalwareRejectedError,
    ObjectKey,
    ObjectLimits,
    OverwriteError,
    ValidationError,
)

KEY = ObjectKey(
    environment="local",
    tenant="tenant-a",
    agent="content",
    run_id="run-1",
    name="draft.md",
)


def make_store(**kwargs: object) -> FakeObjectStore:
    return FakeObjectStore(**kwargs)  # type: ignore[arg-type]


class TestKeysAndPrefixes:
    def test_key_renders_environment_tenant_agent_run_prefix(self) -> None:
        assert KEY.render() == "local/tenant-a/content/run-1/draft.md"

    def test_invalid_segments_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ObjectKey(
                environment="local",
                tenant="../escape",
                agent="content",
                run_id="run-1",
                name="draft.md",
            ).render()

    def test_environment_mismatch_is_rejected_on_put(self) -> None:
        """A store bound to one environment refuses keys from another."""
        store = make_store(environment="local")
        bad = ObjectKey(
            environment="dev",
            tenant="tenant-a",
            agent="content",
            run_id="run-1",
            name="draft.md",
        )
        with pytest.raises(ValidationError):
            store.put(bad, b"data", content_type="text/markdown")


class TestPutGetAndHash:
    def test_put_returns_sha256_and_version(self) -> None:
        store = make_store(environment="local")
        stored = store.put(KEY, b"hello", content_type="text/markdown")
        assert stored.sha256 == hashlib.sha256(b"hello").hexdigest()
        assert stored.version == 1
        assert store.get(KEY).data == b"hello"

    def test_get_verifies_integrity(self) -> None:
        store = make_store(environment="local")
        store.put(KEY, b"hello", content_type="text/markdown")
        retrieved = store.get(KEY)
        assert retrieved.sha256 == hashlib.sha256(b"hello").hexdigest()


class TestNoInPlaceOverwrite:
    def test_put_same_key_creates_a_new_version(self) -> None:
        store = make_store(environment="local")
        first = store.put(KEY, b"v1", content_type="text/markdown")
        second = store.put(KEY, b"v2", content_type="text/markdown")
        assert (first.version, second.version) == (1, 2)
        assert store.get(KEY).data == b"v2"
        assert store.get(KEY, version=1).data == b"v1"

    def test_explicit_version_put_cannot_overwrite_existing_version(self) -> None:
        store = make_store(environment="local")
        store.put(KEY, b"v1", content_type="text/markdown")
        with pytest.raises(OverwriteError):
            store.put(KEY, b"evil", content_type="text/markdown", version=1)

    def test_delete_is_not_supported_in_phase01(self) -> None:
        store = make_store(environment="local")
        assert not hasattr(store, "delete")


class TestLimitsAndScanning:
    def test_oversized_object_is_rejected(self) -> None:
        store = make_store(
            environment="local", limits=ObjectLimits(max_bytes=4, allowed_content_types=None)
        )
        with pytest.raises(ValidationError):
            store.put(KEY, b"too-big", content_type="text/markdown")

    def test_disallowed_content_type_is_rejected(self) -> None:
        store = make_store(
            environment="local",
            limits=ObjectLimits(
                max_bytes=1024, allowed_content_types=frozenset({"text/markdown"})
            ),
        )
        with pytest.raises(ValidationError):
            store.put(KEY, b"x", content_type="application/x-msdownload")

    def test_malware_scan_hook_blocks_the_write(self) -> None:
        def scanner(data: bytes, content_type: str) -> bool:
            return b"EICAR" not in data

        store = make_store(environment="local", malware_scanner=scanner)
        with pytest.raises(MalwareRejectedError):
            store.put(KEY, b"EICAR-test", content_type="text/markdown")
        with pytest.raises(KeyError):
            store.get(KEY)
