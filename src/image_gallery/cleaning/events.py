"""运行时事件与进度回调定义。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class RuntimeEvent:
    """运行时事件载荷。"""

    event_type: str
    run_id: str
    node_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] | None = None
    timestamp: str | None = None


class ProgressReporter:
    """进度事件上报器：仅负责组装事件并回调。"""

    def __init__(self, callback: Callable[[RuntimeEvent], None] | None = None) -> None:
        self._callback = callback

    def emit(
        self,
        event_type: str,
        run_id: str,
        node_id: str | None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        """构造并发送一次运行时事件。"""
        event = RuntimeEvent(
            event_type=event_type,
            run_id=run_id,
            node_id=node_id,
            message=message,
            payload=payload,
            timestamp=_utcnow(),
        )
        if self._callback is not None:
            self._callback(event)
        return event


def _utcnow() -> str:
    """返回带 UTC 时区的 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()
