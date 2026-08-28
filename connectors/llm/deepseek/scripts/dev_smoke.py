"""DEV smoke for the DeepSeek connector — protected pipeline only.

Refuses to run unless enterprise approval evidence and DEV runtime
settings are present in the environment. Without them the real path is
BLOCKED and this script exits non-zero with a typed reason. It never
prints request/response bodies or secret values.

Required environment (provided by the protected DEV pipeline):
  DEEPSEEK_DEV_APPROVAL_EVIDENCE  reference to the recorded approval
  DEEPSEEK_API_ENDPOINT, DEEPSEEK_API_KEY_SECRET_REF (secretref://...),
  DEEPSEEK_CHAT_MODEL, DEEPSEEK_MAX_OUTPUT_TOKENS, DEEPSEEK_RPM,
  DEEPSEEK_TPM, DEEPSEEK_MAX_CONCURRENCY, DEEPSEEK_PER_RUN_BUDGET,
  DEEPSEEK_DAILY_BUDGET, DMT_HTTPS_PROXY, DEEPSEEK_ALLOWED_FQDNS
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "config" / "deepseek.yaml"


def main() -> int:
    approval = os.environ.get("DEEPSEEK_DEV_APPROVAL_EVIDENCE", "").strip()
    if not approval:
        print(
            "BLOCKED: DEEPSEEK_DEV_APPROVAL_EVIDENCE is not set. "
            "DEV smoke only runs in the protected pipeline after enterprise "
            "LLM approval, data-handling review and quota are recorded. "
            "No external HTTP was attempted."
        )
        return 2

    from deepseek_connector.config import load_config, resolve_runtime
    from deepseek_connector.errors import ConnectorConfigError

    config = load_config(CONFIG_PATH)
    if config.mode == "mock" or not config.enabled:
        print(
            "BLOCKED: config/deepseek.yaml still has enabled=false/mode=mock. "
            "Flip it via a reviewed PR in the DEV overlay, not ad hoc."
        )
        return 2
    try:
        runtime = resolve_runtime(config, os.environ)
    except ConnectorConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    # The real transport is injected by the DEV pipeline harness; this
    # repository intentionally ships no real HTTP client for DeepSeek.
    print(
        "READY: config and runtime resolved "
        f"(mode={runtime.mode}, model={runtime.chat_model}, "
        f"config_hash={config.config_hash()}). "
        "Execute the smoke request via the DEV pipeline harness."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
