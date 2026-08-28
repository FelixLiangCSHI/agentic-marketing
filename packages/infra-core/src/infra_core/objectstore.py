"""Object store protocol and in-memory fake.

Keys carry an environment/tenant/agent/run prefix so blast radius is scoped
by construction. Writes are content-hashed, versioned, size/MIME limited,
optionally malware-scanned, and can never overwrite an existing version in
place. There is deliberately no delete in Phase 01.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class ObjectStoreError(Exception):
    """Base class for object store failures."""


class ValidationError(ObjectStoreError):
    """The key, size, or content type is not acceptable."""


class OverwriteError(ObjectStoreError):
    """An existing version can never be overwritten in place."""


class MalwareRejectedError(ObjectStoreError):
    """The malware scan hook rejected the payload."""


_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ObjectKey:
    environment: str
    tenant: str
    agent: str
    run_id: str
    name: str

    def render(self) -> str:
        for segment in (self.environment, self.tenant, self.agent, self.run_id):
            if not _SEGMENT.match(segment):
                raise ValidationError(f"invalid key segment: {segment!r}")
        if not _NAME.match(self.name):
            raise ValidationError(f"invalid object name: {self.name!r}")
        return f"{self.environment}/{self.tenant}/{self.agent}/{self.run_id}/{self.name}"


@dataclass(frozen=True, slots=True)
class ObjectLimits:
    max_bytes: int
    allowed_content_types: frozenset[str] | None  # None -> any type


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    version: int
    sha256: str
    content_type: str
    size: int
    data: bytes


#: Returns True when the payload is clean.
MalwareScanner = Callable[[bytes, str], bool]


class ObjectStore(Protocol):
    def put(
        self,
        key: ObjectKey,
        data: bytes,
        *,
        content_type: str,
        version: int | None = None,
    ) -> StoredObject: ...

    def get(self, key: ObjectKey, *, version: int | None = None) -> StoredObject: ...


@dataclass
class FakeObjectStore:
    """In-memory store enforcing the same invariants as the real binding."""

    environment: str
    limits: ObjectLimits = ObjectLimits(
        max_bytes=10 * 1024 * 1024, allowed_content_types=None
    )
    malware_scanner: MalwareScanner | None = None
    _objects: dict[str, dict[int, StoredObject]] = field(default_factory=dict)

    def put(
        self,
        key: ObjectKey,
        data: bytes,
        *,
        content_type: str,
        version: int | None = None,
    ) -> StoredObject:
        rendered = key.render()
        if key.environment != self.environment:
            raise ValidationError(
                f"store is bound to environment {self.environment!r}; "
                f"refusing key for {key.environment!r}"
            )
        if len(data) > self.limits.max_bytes:
            raise ValidationError(
                f"object exceeds the {self.limits.max_bytes} byte limit"
            )
        allowed = self.limits.allowed_content_types
        if allowed is not None and content_type not in allowed:
            raise ValidationError(f"content type {content_type!r} is not allowed")
        if self.malware_scanner is not None and not self.malware_scanner(
            data, content_type
        ):
            raise MalwareRejectedError("payload was rejected by the malware scan hook")
        versions = self._objects.setdefault(rendered, {})
        if version is not None:
            if version in versions:
                raise OverwriteError(
                    f"version {version} of {rendered!r} already exists and is immutable"
                )
            new_version = version
        else:
            new_version = max(versions, default=0) + 1
        stored = StoredObject(
            key=rendered,
            version=new_version,
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=content_type,
            size=len(data),
            data=bytes(data),
        )
        versions[new_version] = stored
        return stored

    def get(self, key: ObjectKey, *, version: int | None = None) -> StoredObject:
        rendered = key.render()
        versions = self._objects.get(rendered)
        if not versions:
            raise KeyError(rendered)
        chosen = max(versions) if version is None else version
        if chosen not in versions:
            raise KeyError(f"{rendered} @v{chosen}")
        return versions[chosen]
