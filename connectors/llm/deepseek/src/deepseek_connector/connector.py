"""Unified DeepSeek connector.

Interface (per the connector SDK contract):
``validate_config / dry_run / execute / get_status / reconcile / cancel /
normalize_error``. Chat completion is synchronous, so the async job
actions return ``NOT_SUPPORTED`` instead of pretending to support them.

Guarantees:
- mock mode never performs external HTTP (only injected mock transports).
- sandbox/live require enabled config, fully resolved runtime settings,
  an approval evidence reference and an externally provided transport
  (DEV protected pipeline); otherwise a typed ``RealModeBlockedError``.
- Provider failures surface as typed errors — never a silent fallback to
  mock and never fabricated output.
- Retries: bounded exponential backoff + jitter for 408/429/5xx/timeout,
  honoring ``Retry-After``; schema/auth 4xx are never blindly retried.
- The journal records hashes/versions/tokens/cost only — no bodies.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from deepseek_connector.config import DeepSeekConfig, RuntimeSettings, resolve_runtime
from deepseek_connector.contracts import (
    ChatRequestV1,
    ChatResultV1,
    ChatUsageV1,
    FinishReason,
    request_hash,
)
from deepseek_connector.errors import (
    AuthenticationError,
    BudgetExceededError,
    ConnectorErrorV1,
    DeepSeekConnectorError,
    InvalidProviderOutputError,
    LocalQueueFullError,
    NotSupportedError,
    ProviderRateLimitedError,
    ProviderRefusalError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    RealModeBlockedError,
    RequestInvalidError,
    TokenLimitExceededError,
)
from deepseek_connector.governance import BudgetTracker, LocalRateLimiter, estimate_cost
from deepseek_connector.observability import ConnectorJournal, Outcome, RequestRecord
from deepseek_connector.transport import Transport, TransportResponse, TransportTimeout
from infra_core.clock import Clock, SystemClock

Sleeper = Callable[[int], None]


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    mode: str
    enabled: bool
    config_hash: str
    checks: tuple[str, ...]


@dataclass(frozen=True)
class DryRunReport:
    ok: bool
    request_hash: str
    model: str
    estimated_cost: float


@dataclass(frozen=True)
class NotSupportedResult:
    status: Literal["NOT_SUPPORTED"]
    action: str
    reason: str


def _default_sleeper(delay_ms: int) -> None:
    time.sleep(delay_ms / 1000)


class DeepSeekConnector:
    """One configured DeepSeek chat connector instance."""

    connector_kind: Literal["llm"] = "llm"

    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        env: Mapping[str, str],
        transport: Transport,
        clock: Clock | None = None,
        sleeper: Sleeper | None = None,
        rng: random.Random | None = None,
        real_mode_approval_ref: str | None = None,
    ) -> None:
        self._config = config
        self._config_hash = config.config_hash()
        self._runtime: RuntimeSettings = resolve_runtime(config, env)
        if self._runtime.mode != "mock" and not real_mode_approval_ref:
            raise RealModeBlockedError(
                "sandbox/live require a recorded enterprise approval reference; "
                "real path is BLOCKED"
            )
        self._transport = transport
        self._clock = clock or SystemClock()
        self._sleeper = sleeper or _default_sleeper
        self._rng = rng or (
            random.Random(config.mock.deterministic_seed)
            if self._runtime.mode == "mock"
            else random.Random()
        )
        self._limiter = LocalRateLimiter(
            clock=self._clock,
            requests_per_minute=self._runtime.requests_per_minute,
            max_concurrency=self._runtime.max_concurrency,
        )
        self.budget = BudgetTracker(
            per_run_budget=self._runtime.per_run_budget,
            daily_budget=self._runtime.daily_budget,
            clock=self._clock,
            alert_at_percent=config.cost_control.alert_at_percent,
        )
        self.journal = ConnectorJournal()

    @property
    def runtime(self) -> RuntimeSettings:
        return self._runtime

    @property
    def config_hash(self) -> str:
        return self._config_hash

    # ------------------------------------------------------------------
    # Unified connector interface
    # ------------------------------------------------------------------
    def validate_config(self) -> ValidationReport:
        checks = (
            f"schema_version={self._config.schema_version}",
            f"mode={self._runtime.mode}",
            f"enabled={self._config.enabled}",
            "secret=reference-only",
            f"proxy_required={not self._config.network.direct_internet_egress_allowed}",
            f"retry_policy={self._config.retry_strategy.policy}",
        )
        return ValidationReport(
            ok=True,
            mode=self._runtime.mode,
            enabled=self._config.enabled,
            config_hash=self._config_hash,
            checks=checks,
        )

    def dry_run(self, request: ChatRequestV1) -> DryRunReport:
        """Validate a request end-to-end without any transport call."""
        rhash = self._request_hash(request)
        estimated = self._estimate(request)
        self.budget.check_before_request(estimated)
        return DryRunReport(
            ok=True,
            request_hash=rhash,
            model=self._runtime.chat_model,
            estimated_cost=estimated,
        )

    def execute(self, request: ChatRequestV1, *, trace_id: str) -> ChatResultV1:
        if not isinstance(request, ChatRequestV1):
            raise RequestInvalidError("execute requires a ChatRequestV1")
        rhash = self._request_hash(request)
        estimated = self._estimate(request)
        try:
            self.budget.check_before_request(estimated)
        except BudgetExceededError:
            self._record(trace_id, rhash, request, 0, "budget_refused", None, "budget_exceeded")
            raise
        try:
            self._limiter.acquire()
        except LocalQueueFullError:
            self._record(trace_id, rhash, request, 0, "queue_refused", None, "local_queue_full")
            raise
        try:
            return self._execute_with_retry(request, rhash, trace_id)
        finally:
            self._limiter.release()

    def get_status(self, provider_job_id: str) -> NotSupportedResult:
        return NotSupportedResult(
            status="NOT_SUPPORTED",
            action="get_status",
            reason="deepseek chat completion is synchronous; no async job status",
        )

    def reconcile(self, provider_job_id: str) -> NotSupportedResult:
        return NotSupportedResult(
            status="NOT_SUPPORTED",
            action="reconcile",
            reason="deepseek chat completion is synchronous; nothing to reconcile",
        )

    def cancel(self, provider_job_id: str) -> NotSupportedResult:
        return NotSupportedResult(
            status="NOT_SUPPORTED",
            action="cancel",
            reason="deepseek chat completion is synchronous; nothing to cancel",
        )

    def normalize_error(self, error: Exception, *, trace_id: str) -> ConnectorErrorV1:
        """Map any failure onto the frozen connector-error.v1 contract."""
        if isinstance(error, DeepSeekConnectorError):
            code = error.code
            retryable = error.retryable
            message = str(error) or error.code
        else:
            code = "unexpected_error"
            retryable = False
            message = f"{type(error).__name__}: {error}"
        occurred = self._clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        return ConnectorErrorV1(
            connector=self.connector_kind,
            code=code,
            message=message[:2000],
            trace_id=trace_id,
            retryable=retryable,
            details={"provider": "deepseek", "mode": self._runtime.mode},
            occurred_at=occurred,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _request_hash(self, request: ChatRequestV1) -> str:
        return request_hash(
            request, model=self._runtime.chat_model, config_hash=self._config_hash
        )

    def _estimate(self, request: ChatRequestV1) -> float:
        prompt_tokens = sum(len(m.content) for m in request.messages) // 4
        return estimate_cost(prompt_tokens, request.max_output_tokens)

    def _record(
        self,
        trace_id: str,
        rhash: str,
        request: ChatRequestV1,
        attempt: int,
        outcome: Outcome,
        status_code: int | None,
        error_code: str | None,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        retry_delay_ms: int | None = None,
    ) -> None:
        self.journal.append(
            RequestRecord(
                trace_id=trace_id,
                request_hash=rhash,
                mode=self._runtime.mode,
                model=self._runtime.chat_model,
                prompt_version=request.prompt_version,
                config_hash=self._config_hash,
                attempt=attempt,
                outcome=outcome,
                status_code=status_code,
                error_code=error_code,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost=cost,
                retry_delay_ms=retry_delay_ms,
            )
        )

    def _backoff_ms(self, attempt: int, retry_after_s: int | None) -> int:
        strategy = self._config.retry_strategy
        if retry_after_s is not None and strategy.honor_retry_after:
            return min(retry_after_s * 1000, strategy.max_delay_ms)
        base = strategy.initial_delay_ms * (strategy.multiplier ** (attempt - 1))
        capped = min(base, float(strategy.max_delay_ms))
        jitter = self._rng.uniform(0.0, capped / 2)
        return int(min(capped + jitter, float(strategy.max_delay_ms)))

    def _execute_with_retry(
        self, request: ChatRequestV1, rhash: str, trace_id: str
    ) -> ChatResultV1:
        strategy = self._config.retry_strategy
        payload = request.wire_payload(self._runtime.chat_model)
        last_retryable: DeepSeekConnectorError | None = None
        for attempt in range(1, strategy.max_attempts + 1):
            try:
                response = self._transport.send(
                    payload, timeout_ms=self._config.timeouts.request_ms
                )
            except TransportTimeout:
                last_retryable = ProviderTimeoutError(
                    f"provider timeout on attempt {attempt}"
                )
                self._sleep_and_log(request, rhash, trace_id, attempt, None, "provider_timeout")
                continue
            status = response.status_code
            if status in strategy.do_not_retry_http_statuses:
                error: DeepSeekConnectorError
                if status in (401, 403):
                    error = AuthenticationError(f"provider auth failed (HTTP {status})")
                else:
                    error = ProviderRequestError(
                        f"provider rejected the request (HTTP {status}); not retried"
                    )
                self._record(trace_id, rhash, request, attempt, "fatal_failure", status, error.code)
                raise error
            if status in strategy.retry_http_statuses:
                retry_after = _retry_after_seconds(response)
                if status == 429:
                    last_retryable = ProviderRateLimitedError(
                        f"provider rate limited on attempt {attempt}"
                    )
                elif status == 408:
                    last_retryable = ProviderTimeoutError(
                        f"provider request timeout (HTTP 408) on attempt {attempt}"
                    )
                else:
                    last_retryable = ProviderServerError(
                        f"provider server error (HTTP {status}) on attempt {attempt}"
                    )
                self._sleep_and_log(
                    request, rhash, trace_id, attempt, status, last_retryable.code,
                    retry_after_s=retry_after,
                )
                continue
            if status == 200:
                result = self._parse_success(request, response)
                self.budget.record(result.usage.estimated_cost)
                self._record(
                    trace_id,
                    rhash,
                    request,
                    attempt,
                    "success",
                    200,
                    None,
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    cost=result.usage.estimated_cost,
                )
                return result
            unexpected = InvalidProviderOutputError(
                f"unexpected provider HTTP status {status}"
            )
            self._record(trace_id, rhash, request, attempt, "fatal_failure", status, unexpected.code)
            raise unexpected
        assert last_retryable is not None
        raise last_retryable

    def _sleep_and_log(
        self,
        request: ChatRequestV1,
        rhash: str,
        trace_id: str,
        attempt: int,
        status: int | None,
        error_code: str,
        *,
        retry_after_s: int | None = None,
    ) -> None:
        if attempt >= self._config.retry_strategy.max_attempts:
            self._record(trace_id, rhash, request, attempt, "fatal_failure", status, error_code)
            return
        delay = self._backoff_ms(attempt, retry_after_s)
        self._record(
            trace_id, rhash, request, attempt, "retryable_failure", status, error_code,
            retry_delay_ms=delay,
        )
        self._sleeper(delay)

    def _parse_success(
        self, request: ChatRequestV1, response: TransportResponse
    ) -> ChatResultV1:
        try:
            envelope = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise InvalidProviderOutputError("provider body is not JSON") from exc
        try:
            choice = envelope["choices"][0]
            finish_reason = str(choice["finish_reason"])
            content = choice["message"]["content"]
            usage_raw = envelope["usage"]
            prompt_tokens = int(usage_raw["prompt_tokens"])
            completion_tokens = int(usage_raw["completion_tokens"])
            model = str(envelope.get("model", self._runtime.chat_model))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise InvalidProviderOutputError(
                f"provider envelope missing required fields: {exc}"
            ) from exc
        if finish_reason == "content_filter":
            raise ProviderRefusalError("provider refused the request (content filter)")
        if finish_reason == "length":
            raise TokenLimitExceededError(
                "provider output truncated by max token limit; result unusable"
            )
        if finish_reason != "stop" or not isinstance(content, str) or not content:
            raise InvalidProviderOutputError(
                f"unsupported finish_reason or empty content: {finish_reason!r}"
            )
        usage = ChatUsageV1(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=estimate_cost(prompt_tokens, completion_tokens),
        )
        finish: FinishReason = "stop"
        try:
            return ChatResultV1(
                request_id=request.request_id,
                model=model,
                content=content,
                finish_reason=finish,
                usage=usage,
                provider_request_id=_header(response, "x-request-id"),
            )
        except ValidationError as exc:
            raise InvalidProviderOutputError(f"result contract violated: {exc}") from exc


def _header(response: TransportResponse, name: str) -> str | None:
    for key, value in response.headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _retry_after_seconds(response: TransportResponse) -> int | None:
    raw = _header(response, "Retry-After")
    if raw is None:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


__all__ = [
    "DeepSeekConnector",
    "DryRunReport",
    "NotSupportedResult",
    "NotSupportedError",
    "ValidationReport",
]
