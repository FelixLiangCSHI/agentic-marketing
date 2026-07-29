from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from streamlit_demo.data_models import ApplicationConfiguration


CONFIG_PATH_ENV = "AGENTIC_MARKETING_CONFIG_PATH"


class LocalConfigurationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = os.environ.get(CONFIG_PATH_ENV)
        self.path = Path(
            path
            or configured_path
            or Path.home() / ".agentic-marketing" / "config.json"
        ).expanduser()

    def load(self) -> ApplicationConfiguration | None:
        if not self.path.is_file():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return ApplicationConfiguration.from_dict(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return None

    def save(self, configuration: ApplicationConfiguration) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".config-",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                json.dump(
                    configuration.to_dict(),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
