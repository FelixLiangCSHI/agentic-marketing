"""Versioned, append-only package store.

Packages are frozen objects; the store never mutates them. Lifecycle
status (APPROVED → SUPERSEDED / REVOKED) lives in the store's append-only
ledger: publishing a new version supersedes prior versions of the same
lineage, every transition is a new ledger entry (nothing is edited in
place), old versions stay readable for audit, and revocation records a
reason — never a deletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from content_package.contracts import ApprovedContentPackageV1


class PackageStoreError(Exception):
    pass


class UnknownPackageError(PackageStoreError):
    pass


class DuplicateVersionError(PackageStoreError):
    """A different document tried to reuse an existing package id."""


@dataclass(frozen=True)
class LedgerEntry:
    package: ApprovedContentPackageV1
    status: str  # APPROVED | SUPERSEDED | REVOKED
    reason: str
    recorded_at: str


@dataclass
class _Lineage:
    entries: list[LedgerEntry] = field(default_factory=list)


def lineage_key(package: ApprovedContentPackageV1) -> str:
    return f"{package.tenant_id}|{package.product_id}|{package.market}|{package.locale}"


class PackageStore:
    """In-memory append-only ledger with real semantics."""

    def __init__(self) -> None:
        self._lineages: dict[str, _Lineage] = {}
        self._by_id: dict[str, ApprovedContentPackageV1] = {}
        self._status: dict[str, LedgerEntry] = {}

    def publish(
        self, package: ApprovedContentPackageV1, *, recorded_at: str
    ) -> LedgerEntry:
        existing = self._by_id.get(package.package_id)
        if existing is not None:
            if existing.package_hash() != package.package_hash():
                raise DuplicateVersionError(
                    "a different document tried to reuse an existing package id"
                )
            # Idempotent duplicate build: same immutable document, no new entry.
            return self._status[package.package_id]

        key = lineage_key(package)
        lineage = self._lineages.setdefault(key, _Lineage())
        for entry in list(self._status.values()):
            if lineage_key(entry.package) == key and entry.status == "APPROVED":
                self._append(
                    lineage,
                    LedgerEntry(
                        package=entry.package,
                        status="SUPERSEDED",
                        reason=f"superseded by {package.package_id}",
                        recorded_at=recorded_at,
                    ),
                )

        new_entry = LedgerEntry(
            package=package,
            status="APPROVED",
            reason="published",
            recorded_at=recorded_at,
        )
        self._append(lineage, new_entry)
        self._by_id[package.package_id] = package
        return new_entry

    def revoke(self, package_id: str, *, reason: str, recorded_at: str) -> LedgerEntry:
        entry = self._status.get(package_id)
        if entry is None:
            raise UnknownPackageError(package_id)
        revoked = LedgerEntry(
            package=entry.package,
            status="REVOKED",
            reason=reason,
            recorded_at=recorded_at,
        )
        self._append(self._lineages[lineage_key(entry.package)], revoked)
        return revoked

    def get(self, package_id: str) -> LedgerEntry:
        entry = self._status.get(package_id)
        if entry is None:
            raise UnknownPackageError(package_id)
        return entry

    def get_package(self, package_id: str) -> ApprovedContentPackageV1:
        package = self._by_id.get(package_id)
        if package is None:
            raise UnknownPackageError(package_id)
        return package

    def active(self, key: str) -> LedgerEntry | None:
        for entry in self._status.values():
            if lineage_key(entry.package) == key and entry.status == "APPROVED":
                return entry
        return None

    def audit_trail(self, key: str) -> tuple[LedgerEntry, ...]:
        lineage = self._lineages.get(key)
        return tuple(lineage.entries) if lineage else ()

    def _append(self, lineage: _Lineage, entry: LedgerEntry) -> None:
        lineage.entries.append(entry)
        self._status[entry.package.package_id] = entry
