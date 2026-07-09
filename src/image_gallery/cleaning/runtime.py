"""Task 5 的最小运行时组件：事件上报、重试语义和组件级执行占位。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from image_gallery.cleaning.artifacts import ArtifactManager
from image_gallery.cleaning.events import ProgressReporter, RuntimeEvent
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class RunOptions:
    """运行参数。"""

    run_id: str
    retry_max_attempts: int = 1


@dataclass(frozen=True)
class RuntimeRunResult:
    """运行结果摘要。"""

    status: str
    attempt_count: int


class CleaningRuntime:
    """清洗运行时最小骨架。"""

    def __init__(self, cache_root: str | Path) -> None:
        self._cache_root = Path(cache_root)
        self.state_store: SQLiteRunStateStore | None = None
        self._progress = ProgressReporter()
        self._artifact_manager: ArtifactManager | None = None

    def run_graph(
        self,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_options: RunOptions,
    ) -> RuntimeRunResult:
        """占位：当前阶段仅复用测试阶段虚拟节点执行。"""
        del graph
        return self._run_fake_stage_for_test(dataset=dataset, options=run_options, fail_first_attempt=False)

    def run_fake_stage_for_test(
        self,
        dataset: Dataset,
        options: RunOptions,
        fail_first_attempt: bool = False,
    ) -> RuntimeRunResult:
        """仅用于测试的阶段执行入口：用于验证重试、状态存储和事件链路。"""
        if options.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be positive")

        run_id = options.run_id
        run_dir = self._cache_root / run_id
        self._artifact_manager = ArtifactManager(run_dir / "artifacts")
        self.state_store = SQLiteRunStateStore.initialize(
            run_dir=run_dir,
            run_record=RunRecord(
                run_id=run_id,
                cleaner_type="test-runtime",
                status="running",
                dataset_fingerprint=dataset.fingerprint(),
                plan_hash="test-fake-plan",
                label="test-fake",
                tags=[],
                sample_size=None,
                sample_rule=None,
            ),
        )

        self._report(RunEventContext(run_id), "run_started", "runtime", message="runtime started")

        attempt_count = 0
        for attempt in range(1, options.retry_max_attempts + 1):
            attempt_count = attempt
            self._report(
                RunEventContext(run_id),
                "parameter_stage_started",
                "parameter.fake",
                message="stage attempt started",
                payload={"attempt": attempt},
            )
            if attempt == 1 and fail_first_attempt:
                self._report(
                    RunEventContext(run_id),
                    "parameter_stage_failed",
                    "parameter.fake",
                    message="simulated failure",
                    payload={"attempt": attempt},
                )
                continue

            _ = dataset.count()
            self._report(
                RunEventContext(run_id),
                "parameter_stage_completed",
                "parameter.fake",
                message="stage completed",
                payload={"attempt": attempt},
            )
            self._report(
                RunEventContext(run_id),
                "run_completed",
                "runtime",
                message="run completed",
                payload={"attempt_count": attempt},
            )
            return RuntimeRunResult(status="completed", attempt_count=attempt_count)

        self._report(
            RunEventContext(run_id),
            "run_failed",
            "runtime",
            message="run failed",
            payload={"attempt_count": attempt_count},
        )
        return RuntimeRunResult(status="failed", attempt_count=attempt_count)

    def _report(
        self,
        context: RunEventContext,
        event_type: str,
        node_id: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> RuntimeEvent:
        """统一记录并持久化一次 runtime 事件。"""
        event = self._progress.emit(
            event_type=event_type,
            run_id=context.run_id,
            node_id=node_id,
            message=message,
            payload=payload,
        )
        if self.state_store is None:
            raise RuntimeError("state store not initialized")
        self.state_store.record_event(event)
        return event


@dataclass(frozen=True)
class RunEventContext:
    """传递 run_id 的轻量上下文。"""

    run_id: str
