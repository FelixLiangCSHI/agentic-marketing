"""Local governance: RPM window, concurrency, jobs/day, budgets, asset caps.

All limits are enforced client-side before any transport call; the clock
is injected for determinism. Alert at 80%, hard stop at 100%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from infra_core.clock import Clock
from jimeng_connector.errors import BudgetExceededError, LocalQueueFullError

# Synthetic mock pricing per generated image; real pricing is审批事项。
MOCK_COST_PER_IMAGE = 0.02


@dataclass
class JobRateLimiter:
    """RPM window + max in-flight concurrency + jobs-per-day cap."""

    clock: Clock
    requests_per_minute: int
    max_concurrency: int
    jobs_per_day: int
    _window_start: datetime | None = None
    _window_count: int = 0
    _in_flight: int = 0
    _day: str | None = None
    _day_count: int = 0

    def acquire_create(self) -> None:
        now = self.clock.now()
        day = now.strftime("%Y-%m-%d")
        if self._day != day:
            self._day = day
            self._day_count = 0
        if self._day_count >= self.jobs_per_day:
            raise LocalQueueFullError(
                f"jobs-per-day limit {self.jobs_per_day} reached; create refused"
            )
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
        self._day_count += 1
        self._in_flight += 1

    def release(self) -> None:
        if self._in_flight > 0:
            self._in_flight -= 1


@dataclass
class MediaBudget:
    """Per-run/daily cost budgets and per-run asset count cap."""

    per_run_budget: float
    daily_budget: float
    max_assets_per_run: int
    alert_at_percent: int = 80
    run_spent: float = 0.0
    daily_spent: float = 0.0
    run_assets: int = 0
    alerts: list[str] = field(default_factory=list)

    def check_before_create(self, estimated: float) -> None:
        if self.run_assets >= self.max_assets_per_run:
            raise BudgetExceededError(
                f"max assets per run ({self.max_assets_per_run}) reached; create refused"
            )
        if self.run_spent + estimated > self.per_run_budget:
            raise BudgetExceededError("per-run budget would be exceeded; create refused")
        if self.daily_spent + estimated > self.daily_budget:
            raise BudgetExceededError("daily budget would be exceeded; create refused")

    def record_asset(self, actual: float) -> None:
        self.run_assets += 1
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
