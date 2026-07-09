from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatchPolicy:
    """批处理策略。"""

    size: int = 128


@dataclass(frozen=True)
class CheckpointPolicy:
    """Checkpoint 策略。"""

    enabled: bool = True
    strategy: str = "auto"


@dataclass(frozen=True)
class RetryPolicy:
    """失败重试策略。"""

    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retry_on: tuple[str, ...] = ("io_error", "temporary_error", "artifact_commit_error")


@dataclass(frozen=True)
class FailurePolicy:
    """失败处理策略。"""

    fail_fast: bool = False
    max_errors: int | None = None
    bad_image_action: str = "mark_failed"
    retry: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass(frozen=True)
class ResourcePolicy:
    """资源与并发策略。"""

    max_workers: int = 1
    device: str = "auto"


@dataclass(frozen=True)
class CachePolicy:
    """缓存策略。"""

    scope: str = "system"
    reuse: str = "run"
    cleanup: str = "on_success"


@dataclass(frozen=True)
class ArtifactPolicy:
    """产物策略。"""

    retain_intermediate: bool = False
    write_debug_manifest: bool = True


@dataclass(frozen=True)
class ComputerRuntimePolicy:
    """参数计算单元默认运行策略。"""

    batch: BatchPolicy = field(default_factory=BatchPolicy)
    checkpoint: CheckpointPolicy = field(default_factory=CheckpointPolicy)
    failure: FailurePolicy = field(default_factory=FailurePolicy)
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    artifacts: ArtifactPolicy = field(default_factory=ArtifactPolicy)


@dataclass(frozen=True)
class ComputerCapability:
    """参数计算单元能力声明。"""

    checkpoint_strategies: frozenset[str] = frozenset({"batch", "whole_node"})
    supports_batch: bool = True
    supports_retry: bool = True
    produces_artifacts: bool = False
    produces_relations: bool = False


@dataclass(frozen=True)
class NodePolicy:
    """逻辑算子运行策略。"""

    batch: BatchPolicy = field(default_factory=BatchPolicy)
    checkpoint: CheckpointPolicy = field(default_factory=CheckpointPolicy)
    cache: CachePolicy = field(default_factory=CachePolicy)
    failure: FailurePolicy = field(default_factory=FailurePolicy)
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    artifacts: ArtifactPolicy = field(default_factory=ArtifactPolicy)

    @classmethod
    def merge(cls, base: "NodePolicy", override: "NodePolicy") -> "NodePolicy":
        """按 override 覆盖 base 的显式字段并返回新策略。"""
        defaults = cls()
        return cls(
            batch=override.batch if override.batch != defaults.batch else base.batch,
            checkpoint=override.checkpoint if override.checkpoint != defaults.checkpoint else base.checkpoint,
            cache=override.cache if override.cache != defaults.cache else base.cache,
            failure=override.failure if override.failure != defaults.failure else base.failure,
            resources=override.resources if override.resources != defaults.resources else base.resources,
            artifacts=override.artifacts if override.artifacts != defaults.artifacts else base.artifacts,
        )

    @classmethod
    def preset(cls, preset_name: str) -> "NodePolicy":
        """返回内置预设策略。"""
        if preset_name == "fast":
            return cls(batch=BatchPolicy(size=256))
        if preset_name == "balanced":
            return cls()
        if preset_name == "strict":
            return cls(failure=FailurePolicy(fail_fast=True, max_errors=0))
        raise ValueError(f"unknown preset: {preset_name}")
