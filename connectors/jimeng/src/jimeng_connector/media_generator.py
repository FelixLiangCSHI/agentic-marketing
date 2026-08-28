"""Bridge from the Jimeng connector to the Content Workflow media slot.

``JimengMediaGenerator`` implements the ``MediaGenerator`` protocol used
by the ``GenerateMedia`` node, so the workflow can switch between the
fake generator and the (mock or approved-DEV) Jimeng connector without
touching the graph. The synchronous protocol call drives the async
create→poll→download→import pipeline to completion via the durable queue.
"""

from __future__ import annotations

from typing import Callable

from content_workflow.contracts import ContentBriefV1, MediaAssetV1, MediaType
from content_workflow.errors import InvalidNodeOutputError
from jimeng_connector.connector import JimengConnector
from jimeng_connector.contracts import MediaJobRequestV1
from jimeng_connector.errors import JimengConnectorError, NotSupportedError


class JimengMediaGenerator:
    """MediaGenerator implementation backed by the Jimeng connector."""

    def __init__(
        self,
        connector: JimengConnector,
        *,
        max_steps: int = 50,
        wait_fn: Callable[[], None] | None = None,
    ) -> None:
        self._connector = connector
        self._max_steps = max_steps
        self._wait_fn = wait_fn
        self._generator_id = f"jimeng:{connector.runtime.model_id}"

    @property
    def generator_id(self) -> str:
        return self._generator_id

    def generate_media(
        self, brief: ContentBriefV1, media_type: MediaType
    ) -> MediaAssetV1:
        if media_type != "image":
            # 图片模型不得伪装其他媒体能力：类型化 BLOCKED，不虚构。
            raise NotSupportedError(
                f"approved jimeng model only supports image generation, "
                f"not {media_type!r}"
            )
        request = MediaJobRequestV1(
            request_id=brief.request_id,
            run_id=brief.request_id,
            node_id="generate-media",
            tenant=brief.tenant,
            prompt=f"{brief.tone} {brief.objective}"[:8000],
            output_format="png",
            image_count=1,
        )
        try:
            record = self._connector.execute(request)
            steps = 0
            while record.state not in ("COMPLETED", "FAILED", "CANCELLED", "NEEDS_RECONCILE"):
                processed = self._connector.worker.process_once(
                    worker_id="media-generator"
                )
                steps += 1
                if steps > self._max_steps:
                    raise InvalidNodeOutputError(
                        "jimeng mock did not complete within the step budget"
                    )
                if processed is not None:
                    record = processed
                else:
                    if self._wait_fn is not None:
                        # 队列退避重投递前推进时间（测试注入 FakeClock 推进）。
                        self._wait_fn()
                    record = self._connector.get_status(request.idempotency_key())
            self._connector.worker.raise_for_terminal_failure(record)
        except JimengConnectorError as exc:
            # 类型化透传：不静默退回 Fake，由工作流/上层决定返工或阻断。
            raise InvalidNodeOutputError(
                f"jimeng connector failed ({exc.code}): {exc}"
            ) from exc
        if (
            record.state != "COMPLETED"
            or record.asset_object_key is None
            or record.asset_sha256 is None
        ):
            raise InvalidNodeOutputError(
                f"jimeng job ended in state {record.state} without an asset"
            )
        return MediaAssetV1(
            request_id=brief.request_id,
            asset_id=f"asset-{record.asset_sha256[:12]}",
            media_type=media_type,
            uri=f"objectstore://{record.asset_object_key}"
            f"@v{record.asset_object_version}",
            sha256=f"sha256:{record.asset_sha256}",
            alt_text=f"image draft for {brief.objective[:80]}",
            generator_id=self._generator_id,
        )
