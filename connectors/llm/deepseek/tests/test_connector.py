"""Connector contract, fault, retry, budget and observability tests.

All scenarios are deterministic mocks — no external HTTP anywhere.
"""

from __future__ import annotations

import json
import random
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import deepseek_connector.connector as connector_module
from deepseek_connector import (
    AuthenticationError,
    BudgetExceededError,
    ChatMessageV1,
    ChatRequestV1,
    ConnectorErrorV1,
    DeepSeekConnector,
    DeepSeekMockTransport,
    FaultInjection,
    InvalidProviderOutputError,
    LocalQueueFullError,
    ProviderRateLimitedError,
    ProviderRefusalError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    RealModeBlockedError,
    ScriptedTransport,
    TokenLimitExceededError,
    TransportResponse,
    TransportTimeout,
    load_config,
)
from deepseek_connector.governance import BudgetTracker
from deepseek_connector.transport import BRIEF_MARKER, FACTS_MARKER, MockScenario
from infra_core.clock import FakeClock

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "config" / "deepseek.yaml"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "deepseek"


def _request(**overrides: object) -> ChatRequestV1:
    brief = {
        "request_id": "req-0001",
        "channel": "linkedin",
        "objective": "Introduce Product Alpha dosing to physicians",
        "max_headline_chars": 80,
        "required_disclosures": ["See full prescribing information."],
    }
    facts = [{"chunk_hash": "sha256:" + "a" * 64, "text": "Product Alpha is dosed once daily."}]
    base: dict[str, object] = {
        "request_id": "req-0001",
        "prompt_version": "content-copy-prompt/1.0.0",
        "messages": (
            ChatMessageV1(role="system", content="You generate grounded copy."),
            ChatMessageV1(
                role="user",
                content="\n".join(
                    [
                        "Generate.",
                        f"{BRIEF_MARKER}{json.dumps(brief)}",
                        f"{FACTS_MARKER}{json.dumps(facts)}",
                    ]
                ),
            ),
        ),
        "temperature": 0.2,
        "max_output_tokens": 512,
    }
    base.update(overrides)
    return ChatRequestV1.model_validate(base)


def _connector(
    transport: object,
    *,
    env: dict[str, str] | None = None,
    clock: FakeClock | None = None,
) -> DeepSeekConnector:
    sleeps: list[int] = []
    connector = DeepSeekConnector(
        load_config(CONFIG_PATH),
        env=env or {},
        transport=transport,  # type: ignore[arg-type]
        clock=clock or FakeClock(datetime(2026, 8, 28, tzinfo=timezone.utc)),
        sleeper=sleeps.append,
        rng=random.Random(7),
    )
    connector.test_sleeps = sleeps  # type: ignore[attr-defined]
    return connector


def _mock(scenario: MockScenario = "normal", **kwargs: object) -> DeepSeekMockTransport:
    return DeepSeekMockTransport(FIXTURES, scenario=scenario, **kwargs)  # type: ignore[arg-type]


class TestInterface:
    def test_validate_config_reports_safe_defaults(self) -> None:
        report = _connector(_mock()).validate_config()
        assert report.ok and report.mode == "mock" and report.enabled is False
        assert report.config_hash.startswith("sha256:")

    def test_dry_run_makes_no_transport_call(self) -> None:
        transport = _mock()
        report = _connector(transport).dry_run(_request())
        assert report.ok and report.request_hash.startswith("sha256:")
        assert transport.requests_served == 0

    def test_async_actions_return_not_supported(self) -> None:
        connector = _connector(_mock())
        for action in (connector.get_status, connector.reconcile, connector.cancel):
            result = action("job-1")
            assert result.status == "NOT_SUPPORTED"

    def test_real_mode_without_approval_is_blocked(self, tmp_path: Path) -> None:
        import yaml

        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw.update({"mode": "sandbox", "enabled": True})
        path = tmp_path / "deepseek.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        real_env = {
            "DEEPSEEK_API_ENDPOINT": "https://api.deepseek.example",
            "DEEPSEEK_API_KEY_SECRET_REF": "secretref://vault/dev/deepseek-api-key",
            "DEEPSEEK_CHAT_MODEL": "deepseek-chat",
            "DEEPSEEK_MAX_OUTPUT_TOKENS": "2048",
            "DEEPSEEK_RPM": "30",
            "DEEPSEEK_TPM": "60000",
            "DEEPSEEK_MAX_CONCURRENCY": "2",
            "DEEPSEEK_PER_RUN_BUDGET": "1.0",
            "DEEPSEEK_DAILY_BUDGET": "5.0",
            "DMT_HTTPS_PROXY": "http://proxy.internal:3128",
            "DEEPSEEK_ALLOWED_FQDNS": "api.deepseek.example",
        }

        with pytest.raises(RealModeBlockedError):
            DeepSeekConnector(load_config(path), env=real_env, transport=_mock())


class TestMockContract:
    def test_normal_scenario_returns_grounded_structured_result(self) -> None:
        connector = _connector(_mock())
        result = connector.execute(_request(), trace_id="t-normal")
        assert result.finish_reason == "stop"
        draft = json.loads(result.content)
        assert draft["request_id"] == "req-0001"
        assert draft["claims"][0]["chunk_hash"] == "sha256:" + "a" * 64
        assert result.usage.total_tokens == 860
        assert result.provider_request_id == "mock-req-normal"

    def test_refusal_is_typed_not_silent(self) -> None:
        with pytest.raises(ProviderRefusalError):
            _connector(_mock("refusal")).execute(_request(), trace_id="t-refusal")

    def test_invalid_json_content_still_returns_raw_for_caller_validation(self) -> None:
        # 传输层返回 200/stop：内容合法性由调用方(工作流适配层)校验并类型化失败。
        result = _connector(_mock("invalid_json")).execute(_request(), trace_id="t-ij")
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.content)

    def test_token_limit_is_typed_error(self) -> None:
        with pytest.raises(TokenLimitExceededError):
            _connector(_mock("token_limit")).execute(_request(), trace_id="t-tl")


class TestRetries:
    def _success_body(self) -> str:
        fixture = json.loads((FIXTURES / "normal.json").read_text(encoding="utf-8"))
        body = json.dumps(fixture["body"]).replace("[[CONTENT_JSON]]", '{\\"ok\\": true}')
        return body

    def _ok(self) -> TransportResponse:
        return TransportResponse(status_code=200, headers={"x-request-id": "r1"}, body=self._success_body())

    def _resp(self, status: int, headers: dict[str, str] | None = None) -> TransportResponse:
        return TransportResponse(status_code=status, headers=headers or {}, body="{}")

    def test_429_retries_and_honors_retry_after(self) -> None:
        transport = ScriptedTransport([self._resp(429, {"Retry-After": "2"}), self._ok()])
        connector = _connector(transport)
        result = connector.execute(_request(), trace_id="t-429")
        assert result.finish_reason == "stop"
        assert connector.test_sleeps == [2000]  # type: ignore[attr-defined]
        assert len(transport.sent_payloads) == 2
        assert transport.sent_payloads[0] == transport.sent_payloads[1]

    def test_retry_after_is_clamped_to_max_delay(self) -> None:
        transport = ScriptedTransport([self._resp(429, {"Retry-After": "86400"}), self._ok()])
        connector = _connector(transport)
        connector.execute(_request(), trace_id="t-429-clamp")
        assert connector.test_sleeps == [8000]  # type: ignore[attr-defined]

    def test_default_sleeper_uses_time_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        slept: list[float] = []
        monkeypatch.setattr(connector_module.time, "sleep", slept.append)
        connector = DeepSeekConnector(
            load_config(CONFIG_PATH),
            env={},
            transport=ScriptedTransport([self._resp(429, {"Retry-After": "1"}), self._ok()]),
            clock=FakeClock(datetime(2026, 8, 28, tzinfo=timezone.utc)),
            rng=random.Random(7),
        )
        connector.execute(_request(), trace_id="t-default-sleeper")
        assert slept == [1.0]

    def test_real_mode_default_rng_uses_entropy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        random_args: list[object] = []
        original_random = connector_module.random.Random

        def spy_random(seed: object = None) -> random.Random:
            random_args.append(seed)
            return original_random(seed)

        monkeypatch.setattr(connector_module.random, "Random", spy_random)
        config = load_config(CONFIG_PATH).model_copy(update={"mode": "sandbox", "enabled": True})
        DeepSeekConnector(
            config,
            env={
                "DEEPSEEK_API_ENDPOINT": "https://api.deepseek.example",
                "DEEPSEEK_API_KEY_SECRET_REF": "secretref://vault/dev/deepseek-api-key",
                "DEEPSEEK_CHAT_MODEL": "deepseek-chat",
                "DEEPSEEK_MAX_OUTPUT_TOKENS": "2048",
                "DEEPSEEK_RPM": "30",
                "DEEPSEEK_TPM": "60000",
                "DEEPSEEK_MAX_CONCURRENCY": "2",
                "DEEPSEEK_PER_RUN_BUDGET": "1.0",
                "DEEPSEEK_DAILY_BUDGET": "5.0",
                "DMT_HTTPS_PROXY": "http://proxy.internal:3128",
                "DEEPSEEK_ALLOWED_FQDNS": "api.deepseek.example",
            },
            transport=ScriptedTransport([self._ok()]),
            real_mode_approval_ref="approval://dev/deepseek/1",
        )
        assert random_args == [None]

    def test_5xx_bounded_exponential_backoff_then_typed_exhaustion(self) -> None:
        transport = ScriptedTransport([self._resp(503)] * 4)
        connector = _connector(transport)
        with pytest.raises(ProviderServerError):
            connector.execute(_request(), trace_id="t-5xx")
        sleeps = connector.test_sleeps  # type: ignore[attr-defined]
        assert len(sleeps) == 3  # max_attempts=4 -> 3 backoffs
        assert all(s <= 8000 for s in sleeps)
        assert sleeps[0] < sleeps[1] < sleeps[2]

    def test_timeout_retried_then_typed(self) -> None:
        transport = ScriptedTransport([TransportTimeout("t")] * 4)
        with pytest.raises(ProviderTimeoutError):
            _connector(transport).execute(_request(), trace_id="t-to")

    def test_429_exhaustion_is_rate_limited_error(self) -> None:
        transport = ScriptedTransport([self._resp(429)] * 4)
        with pytest.raises(ProviderRateLimitedError):
            _connector(transport).execute(_request(), trace_id="t-429x")

    def test_400_schema_error_never_retried(self) -> None:
        transport = ScriptedTransport([self._resp(400)])
        with pytest.raises(ProviderRequestError):
            _connector(transport).execute(_request(), trace_id="t-400")
        assert len(transport.sent_payloads) == 1

    def test_401_auth_error_never_retried(self) -> None:
        transport = ScriptedTransport([self._resp(401)])
        with pytest.raises(AuthenticationError):
            _connector(transport).execute(_request(), trace_id="t-401")
        assert len(transport.sent_payloads) == 1

    def test_fault_injection_is_deterministic_and_recovers(self) -> None:
        faults = FaultInjection(enabled=True, timeout_rate=1.0)
        connector = _connector(_mock("normal", seed=3, faults=faults))
        result = connector.execute(_request(), trace_id="t-fault")
        assert result.finish_reason == "stop"
        retryable = [r for r in connector.journal.records if r.outcome == "retryable_failure"]
        assert len(retryable) == 1 and retryable[0].error_code == "provider_timeout"


class TestGovernance:
    def test_budget_stop_refuses_before_any_transport_call(self) -> None:
        transport = _mock()
        connector = _connector(
            transport, env={"DEEPSEEK_PER_RUN_BUDGET": "0.0000001", "DEEPSEEK_DAILY_BUDGET": "10"}
        )
        with pytest.raises(BudgetExceededError):
            connector.execute(_request(), trace_id="t-budget")
        assert transport.requests_served == 0
        assert connector.journal.records[-1].outcome == "budget_refused"

    def test_budget_alert_recorded_at_threshold(self) -> None:
        connector = _connector(_mock())
        connector.budget.record(connector.budget.per_run_budget * 0.85)
        assert any("per_run" in alert for alert in connector.budget.alerts)

    def test_budget_record_is_thread_safe(self) -> None:
        budget = BudgetTracker(per_run_budget=100.0, daily_budget=100.0)

        def record_many() -> None:
            for _ in range(1000):
                budget.record(0.001)

        threads = [threading.Thread(target=record_many) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert budget.run_spent == 20.0
        assert budget.daily_spent == 20.0

    def test_daily_budget_rolls_over_on_utc_date_change(self) -> None:
        clock = FakeClock(datetime(2026, 8, 28, 23, 59, tzinfo=timezone.utc))
        connector = _connector(
            _mock(),
            env={"DEEPSEEK_PER_RUN_BUDGET": "10.0", "DEEPSEEK_DAILY_BUDGET": "1.0"},
            clock=clock,
        )
        connector.budget.record(0.9)
        with pytest.raises(BudgetExceededError, match="daily budget"):
            connector.budget.check_before_request(0.2)

        clock.advance(timedelta(minutes=2))
        connector.budget.check_before_request(0.2)
        connector.budget.record(0.2)
        assert connector.budget.daily_spent == 0.2

    def test_rpm_limit_hits_local_queue(self) -> None:
        connector = _connector(_mock(), env={"DEEPSEEK_RPM": "1"})
        connector.execute(_request(), trace_id="t-rpm-1")
        with pytest.raises(LocalQueueFullError):
            connector.execute(_request(), trace_id="t-rpm-2")

    def test_journal_records_hashes_versions_costs_but_no_bodies(self) -> None:
        connector = _connector(_mock())
        connector.execute(_request(), trace_id="t-journal")
        record = connector.journal.records[-1]
        assert record.outcome == "success"
        assert record.request_hash.startswith("sha256:")
        assert record.prompt_version == "content-copy-prompt/1.0.0"
        assert record.config_hash == connector.config_hash
        assert record.prompt_tokens == 640 and record.completion_tokens == 220
        assert record.estimated_cost > 0
        dumped = json.dumps(record.__dict__)
        assert "Product Alpha is dosed" not in dumped
        assert "secretref" not in dumped


class TestNormalizeError:
    def test_typed_error_maps_to_connector_error_v1(self) -> None:
        connector = _connector(_mock())
        error = connector.normalize_error(
            ProviderServerError("provider server error (HTTP 503)"), trace_id="t-ne"
        )
        assert isinstance(error, ConnectorErrorV1)
        assert error.connector == "llm"
        assert error.code == "provider_server_error"
        assert error.retryable is True
        assert error.trace_id == "t-ne"

    def test_unknown_error_maps_to_unexpected(self) -> None:
        error = _connector(_mock()).normalize_error(ValueError("boom"), trace_id="t-ue")
        assert error.code == "unexpected_error"
        assert error.retryable is False

    def test_normalize_error_sanitizes_credential_material(self) -> None:
        error = _connector(_mock()).normalize_error(
            ValueError("api_key: sk-verysecret1234567890 leaked"), trace_id="t-sm"
        )
        assert "sk-verysecret1234567890" not in error.message
        assert "[redacted]" in error.message


    def test_invalid_provider_output_normalizes(self) -> None:
        error = _connector(_mock()).normalize_error(
            InvalidProviderOutputError("bad envelope"), trace_id="t-io"
        )
        assert error.code == "invalid_provider_output"
