from __future__ import annotations

import copy
from typing import Any, Literal


ApprovalStatus = Literal["draft", "approved", "rejected"]


class ApprovalEngine:
    def update_insight(
        self,
        analysis: dict[str, Any],
        insight_id: str,
        status: ApprovalStatus,
    ) -> dict[str, Any]:
        updated = copy.deepcopy(analysis)
        bundle = updated.get("strategyBundle", {})
        for insight in bundle.get("insights", []):
            if insight.get("insightId") == insight_id:
                insight["approvalStatus"] = status
        if status != "approved":
            for strategy in bundle.get("strategies", []):
                if insight_id in strategy.get("insightIds", []):
                    strategy["approvalStatus"] = "draft"
        return updated

    def update_strategy(
        self,
        analysis: dict[str, Any],
        strategy_id: str,
        status: ApprovalStatus,
    ) -> dict[str, Any]:
        updated = copy.deepcopy(analysis)
        for strategy in updated.get("strategyBundle", {}).get("strategies", []):
            if strategy.get("strategyId") == strategy_id:
                strategy["approvalStatus"] = status
        return updated

