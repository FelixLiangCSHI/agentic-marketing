"""DEV smoke for the Jimeng connector — protected pipeline only.

Refuses to run unless official vendor approval evidence and DEV runtime
settings are present. Without them the real path is BLOCKED and this
script exits non-zero with a typed reason. It never prints prompts,
result URLs or secret values, and never attempts HTTP itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "jimeng.yaml"


def main() -> int:
    approval = os.environ.get("JIMENG_DEV_APPROVAL_EVIDENCE", "").strip()
    if not approval:
        print(
            "BLOCKED: JIMENG_DEV_APPROVAL_EVIDENCE is not set. DEV smoke only "
            "runs in the protected pipeline after the official vendor, "
            "region/tenant, auth, image model and data retention/training "
            "policies are confirmed and recorded. No external HTTP was attempted."
        )
        return 2

    from jimeng_connector.config import load_config, resolve_runtime
    from jimeng_connector.errors import ConnectorConfigError, ForbiddenAuthError

    config = load_config(CONFIG_PATH)
    if config.mode == "mock" or not config.enabled:
        print(
            "BLOCKED: config/jimeng.yaml still has enabled=false/mode=mock. "
            "Flip it via a reviewed PR in the DEV overlay, not ad hoc."
        )
        return 2
    try:
        runtime = resolve_runtime(config, os.environ)
    except ForbiddenAuthError as exc:
        print(f"FAIL: {exc}")
        return 1
    except ConnectorConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    # The real transport is injected by the DEV pipeline harness; this
    # repository intentionally ships no real HTTP client for Jimeng.
    print(
        "READY: config and runtime resolved "
        f"(mode={runtime.mode}, tenant={runtime.tenant_variant}, "
        f"model={runtime.model_id}, config_hash={config.config_hash()}). "
        "Execute the smoke job via the DEV pipeline harness."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
