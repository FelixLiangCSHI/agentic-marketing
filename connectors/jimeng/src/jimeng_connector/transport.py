"""Provider transports: the only layer that would touch the network.

Only the deterministic async mock exists in the repository — no real HTTP
client is implemented. The real transport (official Volcengine/BytePlus
enterprise API, vendor-signed requests through the proxy) is injected by
the approved DEV pipeline. Cookie or reverse-engineered access is never
implemented anywhere.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Protocol

from jimeng_connector.contracts import MediaJobRequestV1, mime_for_format
from jimeng_connector.errors import ConnectorConfigError


class TransportTimeout(Exception):
    """Connect/request deadline exceeded (may still have side effects)."""


@dataclass(frozen=True)
class ProviderJob:
    provider_job_id: str
    state: Literal["running", "completed", "failed", "cancelled"]
    failure_code: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    """Result reference returned by the provider once a job completes."""

    provider_job_id: str
    url: str
    content_type: str
    content_sha256: str
    url_issued_at_poll: int


@dataclass(frozen=True)
class DownloadedAsset:
    data: bytes
    content_type: str
    tls_verified: bool


class MediaTransport(Protocol):
    """Official-API surface used by the worker; mock in repo/CI."""

    def create_job(self, request: MediaJobRequestV1, *, idempotency_key: str) -> ProviderJob: ...

    def find_job(self, *, idempotency_key: str) -> ProviderJob | None: ...

    def get_status(self, provider_job_id: str) -> ProviderJob: ...

    def get_result(self, provider_job_id: str) -> ProviderResult: ...

    def download(self, result: ProviderResult) -> DownloadedAsset: ...

    def cancel_job(self, provider_job_id: str) -> ProviderJob: ...


MockScenario = Literal[
    "completed",
    "failed_job",
    "cancelled",
    "rate_limited_create",
    "timeout_but_created",
    "url_expired",
    "invalid_mime",
    "malware",
    "unknown_job",
]


class RateLimited(Exception):
    """HTTP 429 from the provider; carries Retry-After seconds."""

    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"rate limited; retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


@dataclass
class _MockJob:
    provider_job_id: str
    request: MediaJobRequestV1
    polls: int = 0
    state: str = "running"
    cancelled: bool = False


# EICAR-like synthetic marker; the fake scanner rejects payloads containing it.
MALWARE_MARKER = b"X5O!SYNTHETIC-MALWARE-FIXTURE"


class JimengMockTransport:
    """Deterministic async mock of the official Jimeng image API.

    Never opens a socket. Jobs complete after ``complete_after_polls``
    status calls. Duplicate creates with the same idempotency key always
    return the existing job. ``timeout_but_created`` raises a timeout on
    create while still registering the job, so reconcile-before-retry can
    be proven. Result URLs expire after ``url_ttl_polls`` further polls.
    """

    def __init__(
        self,
        fixture_dir: Path,
        *,
        scenario: MockScenario = "completed",
        complete_after_polls: int = 2,
        url_ttl_polls: int = 100,
    ) -> None:
        if not fixture_dir.is_dir():
            raise ConnectorConfigError(f"mock fixture_dir not found: {fixture_dir}")
        self._asset_path = fixture_dir / "generated" / "sample-approved.png"
        if not self._asset_path.is_file():
            raise ConnectorConfigError(f"missing generated asset fixture: {self._asset_path}")
        self._scenario: MockScenario = scenario
        self._complete_after = complete_after_polls
        self._url_ttl_polls = url_ttl_polls
        self._jobs: dict[str, _MockJob] = {}
        self._by_idempotency: dict[str, str] = {}
        self._counter = 0
        self.create_calls = 0
        self.status_calls = 0
        self.download_calls = 0

    # -- create -------------------------------------------------------
    def create_job(self, request: MediaJobRequestV1, *, idempotency_key: str) -> ProviderJob:
        self.create_calls += 1
        existing_id = self._by_idempotency.get(idempotency_key)
        if existing_id is not None:
            job = self._jobs[existing_id]
            return ProviderJob(provider_job_id=job.provider_job_id, state="running")
        if self._scenario == "rate_limited_create":
            raise RateLimited(retry_after_s=1)
        self._counter += 1
        job_id = f"mock-job-{hashlib.sha256(idempotency_key.encode()).hexdigest()[:12]}"
        self._jobs[job_id] = _MockJob(provider_job_id=job_id, request=request)
        self._by_idempotency[idempotency_key] = job_id
        if self._scenario == "timeout_but_created":
            # 任务已在供应商侧创建，但响应超时:必须先对账，不得重复创建。
            self._scenario = "completed"
            raise TransportTimeout("create timed out after the job was registered")
        return ProviderJob(provider_job_id=job_id, state="running")

    def find_job(self, *, idempotency_key: str) -> ProviderJob | None:
        job_id = self._by_idempotency.get(idempotency_key)
        if job_id is None:
            return None
        job = self._jobs[job_id]
        state = "cancelled" if job.cancelled else ("running" if job.polls < self._complete_after else "completed")
        return ProviderJob(provider_job_id=job_id, state=state)  # type: ignore[arg-type]

    # -- status / result ---------------------------------------------
    def get_status(self, provider_job_id: str) -> ProviderJob:
        self.status_calls += 1
        if self._scenario == "unknown_job" or provider_job_id not in self._jobs:
            from jimeng_connector.errors import UnknownJobError

            raise UnknownJobError(f"provider does not know job {provider_job_id}")
        job = self._jobs[provider_job_id]
        if job.cancelled or self._scenario == "cancelled":
            return ProviderJob(provider_job_id=provider_job_id, state="cancelled")
        job.polls += 1
        if job.polls < self._complete_after:
            return ProviderJob(provider_job_id=provider_job_id, state="running")
        if self._scenario == "failed_job":
            return ProviderJob(
                provider_job_id=provider_job_id,
                state="failed",
                failure_code="generation_failed",
            )
        return ProviderJob(provider_job_id=provider_job_id, state="completed")

    def get_result(self, provider_job_id: str) -> ProviderResult:
        job = self._jobs[provider_job_id]
        data = self._payload(job)
        content_type = (
            "application/octet-stream"
            if self._scenario == "invalid_mime"
            else mime_for_format(job.request.output_format)
        )
        return ProviderResult(
            provider_job_id=provider_job_id,
            url=f"https://mock-cdn.jimeng.example/{provider_job_id}",
            content_type=content_type,
            content_sha256=hashlib.sha256(data).hexdigest(),
            url_issued_at_poll=job.polls,
        )

    def download(self, result: ProviderResult) -> DownloadedAsset:
        self.download_calls += 1
        job = self._jobs[result.provider_job_id]
        if self._scenario == "url_expired" and job.polls - result.url_issued_at_poll >= 0:
            # 临时 URL 过期一次后恢复：重新获取 result 引用即可，不得重建 Job。
            self._scenario = "completed"
            from jimeng_connector.errors import ResultUrlExpiredError

            raise ResultUrlExpiredError("temporary result URL expired")
        return DownloadedAsset(
            data=self._payload(job),
            content_type=result.content_type,
            tls_verified=result.url.startswith("https://"),
        )

    def cancel_job(self, provider_job_id: str) -> ProviderJob:
        job = self._jobs[provider_job_id]
        job.cancelled = True
        return ProviderJob(provider_job_id=provider_job_id, state="cancelled")

    def _payload(self, job: _MockJob) -> bytes:
        base = self._asset_path.read_bytes()
        if self._scenario == "malware":
            return base + MALWARE_MARKER
        # 每个 job 的资产内容确定但互不相同（附加 job 指纹注释字节）。
        return base + job.provider_job_id.encode("ascii")
