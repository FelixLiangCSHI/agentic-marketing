from __future__ import annotations

import base64
import itertools
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_SIZE_BYTES = 25 * 1024 * 1024
PROTOCOL_VERSION = "1.0"
_REQUEST_COUNTER = itertools.count(1)


@dataclass(frozen=True)
class BridgeFailure:
    code: str
    message: str
    retryable: bool
    preserve_project_data: bool
    next_action: str


class BridgeClientError(RuntimeError):
    def __init__(self, failure: BridgeFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


def _failure(
    code: str,
    message: str,
    next_action: str,
    *,
    retryable: bool = True,
    preserve_project_data: bool = True,
) -> BridgeClientError:
    return BridgeClientError(
        BridgeFailure(
            code=code,
            message=message,
            retryable=retryable,
            preserve_project_data=preserve_project_data,
            next_action=next_action,
        )
    )


def _node_candidates() -> list[Path]:
    candidates: list[Path] = []
    discovered = shutil.which("node")
    if discovered:
        candidates.append(Path(discovered))

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            winget_root = (
                Path(local_app_data)
                / "Microsoft"
                / "WinGet"
                / "Packages"
            )
            candidates.extend(
                sorted(
                    winget_root.glob(
                        "OpenJS.NodeJS.LTS_*/*/node.exe"
                    ),
                    reverse=True,
                )
            )
        candidates.extend(
            [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
                / "nodejs"
                / "node.exe",
                Path(
                    os.environ.get(
                        "ProgramFiles(x86)", "C:\\Program Files (x86)"
                    )
                )
                / "nodejs"
                / "node.exe",
            ]
        )

    return candidates


def resolve_node_executable(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate.resolve()
        raise _failure(
            "BRIDGE_UNAVAILABLE",
            "指定的 Node.js 可执行文件不存在。",
            "请修正 Node.js 路径后重试。",
            retryable=False,
        )

    for candidate in _node_candidates():
        if candidate.is_file():
            return candidate.resolve()

    raise _failure(
        "BRIDGE_UNAVAILABLE",
        "未找到 Node.js，无法调用确定性分析核心。",
        "请安装 Node.js 12 或更高版本；本地开发推荐 Node.js 24 LTS。",
        retryable=False,
    )


def encode_upload(
    *,
    slot: str,
    name: str,
    mime_type: str,
    data: bytes,
) -> dict[str, Any]:
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise _failure(
            "REQUEST_TOO_LARGE",
            "文件超过 10 MB 限制。",
            "请选择更小的 LinkedIn 导出文件。",
        )

    mutable = bytearray(data)
    try:
        encoded = base64.b64encode(mutable).decode("ascii")
    finally:
        mutable[:] = b"\x00" * len(mutable)

    return {
        "slot": slot,
        "name": Path(name).name[:300],
        "mimeType": mime_type[:200],
        "size": len(data),
        "base64": encoded,
    }


def _restricted_environment() -> dict[str, str]:
    blocked_fragments = (
        "API_KEY",
        "AUTHORIZATION",
        "PASSWORD",
        "SECRET",
        "TOKEN",
    )
    return {
        key: value
        for key, value in os.environ.items()
        if not any(fragment in key.upper() for fragment in blocked_fragments)
    }


class BridgeClient:
    def __init__(
        self,
        repo_root: str | Path | None = None,
        *,
        node_executable: str | Path | None = None,
        default_timeout_seconds: float = 45.0,
    ) -> None:
        self.repo_root = (
            Path(repo_root)
            if repo_root is not None
            else Path(__file__).resolve().parents[1]
        ).resolve()
        self.node_executable = resolve_node_executable(node_executable)
        self.default_timeout_seconds = default_timeout_seconds
        self.tsx_cli = self.repo_root / "node_modules" / "tsx" / "dist" / "cli.mjs"
        self.source_bridge = (
            self.repo_root / "scripts" / "streamlit-bridge.ts"
        )

        if self.tsx_cli.is_file() and self.source_bridge.is_file():
            self.command = [
                str(self.node_executable),
                str(self.tsx_cli),
                str(self.source_bridge),
            ]
        else:
            raise _failure(
                "BRIDGE_UNAVAILABLE",
                "找不到可运行的 Node Bridge。",
                "请在项目目录运行 npm install 以安装 tsx，"
                "并确认 scripts/streamlit-bridge.ts 存在。",
                retryable=False,
            )

    def call(
        self,
        operation: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        request_id = f"streamlit-{os.getpid()}-{next(_REQUEST_COUNTER)}"
        request = {
            "requestId": request_id,
            "operation": operation,
            "payload": payload or {},
        }
        serialized = json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            completed = subprocess.run(
                self.command,
                input=serialized,
                cwd=self.repo_root,
                env=_restricted_environment(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=timeout_seconds or self.default_timeout_seconds,
                check=False,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )
        except subprocess.TimeoutExpired as reason:
            code = (
                "AI_TIMEOUT"
                if operation in {"create_plan", "answer_question"}
                else "BRIDGE_UNAVAILABLE"
            )
            raise _failure(
                code,
                "本地分析阶段响应超时。",
                "当前项目数据仍在内存中，可直接重试本阶段。",
            ) from reason
        except (OSError, UnicodeError) as reason:
            raise _failure(
                "BRIDGE_UNAVAILABLE",
                "无法启动本地分析 Bridge。",
                "请确认 Node.js 与 npm 依赖可用后重试。",
            ) from reason

        stdout = completed.stdout
        if completed.returncode != 0:
            raise _failure(
                "BRIDGE_UNAVAILABLE",
                "本地分析 Bridge 异常退出。",
                "当前项目数据仍保留，请检查 npm install 后重试。",
            )
        if len(stdout.encode("utf-8")) > MAX_RESPONSE_SIZE_BYTES:
            raise _failure(
                "INVALID_MODEL_OUTPUT",
                "Bridge 返回内容超过安全限制。",
                "请减少输入文件大小并重试。",
            )

        try:
            response = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as reason:
            raise _failure(
                "INVALID_MODEL_OUTPUT",
                "Bridge 返回了无效结构。",
                "当前项目数据仍保留，可重试或改用 Synthetic Demo。",
            ) from reason

        if (
            not isinstance(response, dict)
            or response.get("protocolVersion") != PROTOCOL_VERSION
            or response.get("requestId") != request_id
            or not isinstance(response.get("success"), bool)
        ):
            raise _failure(
                "INVALID_MODEL_OUTPUT",
                "Bridge 协议校验失败。",
                "当前项目数据仍保留，请重启 Streamlit 后重试。",
            )

        if response["success"] is False:
            error = response.get("error")
            if not isinstance(error, dict):
                raise _failure(
                    "INVALID_MODEL_OUTPUT",
                    "Bridge 错误结构无效。",
                    "当前项目数据仍保留，请重试。",
                )
            raise BridgeClientError(
                BridgeFailure(
                    code=str(error.get("code", "INTERNAL_ERROR")),
                    message=str(
                        error.get("message", "本地分析处理失败。")
                    ),
                    retryable=bool(error.get("retryable", True)),
                    preserve_project_data=bool(
                        error.get("preserveProjectData", True)
                    ),
                    next_action=str(
                        error.get(
                            "nextAction",
                            "请修正输入后重试当前阶段。",
                        )
                    ),
                )
            )

        data = response.get("data")
        if not isinstance(data, dict):
            raise _failure(
                "INVALID_MODEL_OUTPUT",
                "Bridge 成功响应缺少数据对象。",
                "当前项目数据仍保留，请重试。",
            )
        return data
