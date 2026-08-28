"""Local governance: rate limiting, concurrency and cost budgets.

All limits are enforced client-side before any transport call. The clock
is injected so behavior is deterministic in tests. No wall-clock sleeps
happen here; callers receive typed errors when limits are hit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from deepseek_connector.errors import BudgetExceededError, LocalQueueFullError
from infra_core.clock import Clock


@dataclass
class LocalRateLimiter:
    """Requests-per-minute window + max in-flight concurrency."""

    clock: Clock
    requests_per_minute: int
    max_concurrency: int
    _window_start: datetime | None = None
    _window_count: int = 0
    _in_flight: int = 0

    def acquire(self) -> None:
        now = self.clock.now()
        if self._window_start is None or (now - self._window_start).total_seconds() >= 60:
            self._window_start = now
            self._window_count = 0
        if self._window_count >= self.requests_per_minute:
            raise LocalQueueFullError(
                f"local RPM limit {self.requests_per_minute} reached; request queued/rejected"
            )
        if self._in_flight >= self.max_concurrency:
            raise LocalQueueFullError(
                f"max concurrency {self.max_concurrency} reached; request queued/rejected"
            )
        self._window_count += 1
        self._in_flight += 1

    def release(self) -> None:
        if self._in_flight > 0:
            self._in_flight -= 1


# Synthetic mock pricing (per 1K tokens); real pricing is配置/审批事项。
MOCK_COST_PER_1K_PROMPT = 0.00014
MOCK_COST_PER_1K_COMPLETION = 0.00028


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens / 1000 * MOCK_COST_PER_1K_PROMPT
        + completion_tokens / 1000 * MOCK_COST_PER_1K_COMPLETION,
        8,
    )


@dataclass
class BudgetTracker:
    """Per-run and daily budgets with alert (80%) and hard stop (100%)."""

    per_run_budget: float
    daily_budget: float
    alert_at_percent: int = 80
    run_spent: float = 0.0
    daily_spent: float = 0.0
    alerts: list[str] = field(default_factory=list)

    def check_before_request(self, estimated: float) -> None:
        if self.run_spent + estimated > self.per_run_budget:
            raise BudgetExceededError(
                "per-run budget would be exceeded; request refused"
            )
        if self.daily_spent + estimated > self.daily_budget:
            raise BudgetExceededError("daily budget would be exceeded; request refused")

    def record(self, actual: float) -> None:
        self.run_spent = round(self.run_spent + actual, 8)
        self.daily_spent = round(self.daily_spent + actual, 8)
        for scope, spent, budget in (
            ("per_run", self.run_spent, self.per_run_budget),
            ("daily", self.daily_spent, self.daily_budget),
        ):
            if spent >= budget * self.alert_at_percent / 100 and not any(
                alert.startswith(scope) for alert in self.alerts
            ):
                self.alerts.append(
                    f"{scope} budget at {spent / budget * 100:.0f}% "
                    f"(alert threshold {self.alert_at_percent}%)"
                )
