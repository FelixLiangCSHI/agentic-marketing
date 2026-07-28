from __future__ import annotations

from typing import Final


AI_INSIGHT_CONNECTION_PROMPT: Final = (
    "Validate that the configured insight service can prepare evidence-based "
    "marketing insights."
)
AI_PLAN_CONNECTION_PROMPT: Final = (
    "Validate that the configured planning service can prepare a governed "
    "30-day campaign plan."
)

PROMPT_TEMPLATES: Final = {
    "ai_insight": AI_INSIGHT_CONNECTION_PROMPT,
    "ai_plan": AI_PLAN_CONNECTION_PROMPT,
}

