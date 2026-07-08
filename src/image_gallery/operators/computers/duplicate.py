from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult


@dataclass
class _PerceptualGroup:
    """视觉近重复组的内部状态。"""

    keeper_image_id: str
    keeper_phash: str
    members: list[str]


@dataclass(frozen=True)
class _PerceptualAssignment:
    """单张图片到视觉近重复组的内部映射。"""

    image_id: str
    group_index: int | None
    distance: int | None


@dataclass(frozen=True)
class _PerceptualPair:
    """视觉近重复 relation 的内部行。"""

    source_image_id: str
    target_image_id: str
    distance: int
    group_id: str


class DuplicateGroupComputer(ParameterComputer):
    """基于 content_hash 生产完全重复分组。"""

    name = "duplicate_group_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"exact_duplicate_group_id", "exact_duplicate_count"})
    required_parameters = frozenset({"content_hash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产完全重复组参数和 pair relation。"""
        frame = request.parameter_table[["image_id", "content_hash"]].copy()
        valid_hash = frame["content_hash"].fillna("").astype(str) != ""
        counts = frame.loc[valid_hash, "content_hash"].value_counts()
        duplicate_hashes = {hash_value for hash_value, count in counts.items() if int(count) > 1}

        rows: list[dict[str, object]] = []
        for row in frame.to_dict(orient="records"):
            content_hash = str(row.get("content_hash") or "")
            count = int(counts.get(content_hash, 1)) if content_hash else 1
            group_id = f"exact-{content_hash}" if content_hash in duplicate_hashes else ""
            rows.append(
                {
                    "image_id": row["image_id"],
                    "exact_duplicate_group_id": group_id,
                    "exact_duplicate_count": count,
                }
            )

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={"duplicate_pairs": _build_duplicate_pairs(frame, duplicate_hashes)},
            artifact_refs={},
            parameter_manifest={
                parameter: {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["content_hash"],
                }
                for parameter in sorted(self.produced_parameters)
            },
        )


class PerceptualDuplicateGroupComputer(ParameterComputer):
    """基于 pHash 距离生产视觉近重复分组。"""

    name = "perceptual_duplicate_group_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset(
        {"perceptual_duplicate_group_id", "perceptual_duplicate_count", "perceptual_duplicate_distance"}
    )
    required_parameters = frozenset({"phash"})
    config_parameters = frozenset({"max_distance"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产视觉近重复组参数和 pair relation。"""
        max_distance = _as_int(request.config.get("max_distance", 4))
        frame = request.parameter_table[["image_id", "phash"]].copy()
        group_rows, pair_rows = _build_perceptual_groups(frame, max_distance)

        return ParameterResult(
            parameter_updates=pd.DataFrame(group_rows),
            relation_updates={"perceptual_duplicate_pairs": _build_perceptual_duplicate_pairs(pair_rows)},
            artifact_refs={},
            parameter_manifest={
                parameter: {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["phash"],
                    "max_distance": max_distance,
                }
                for parameter in sorted(self.produced_parameters)
            },
        )


def _build_duplicate_pairs(frame: pd.DataFrame, duplicate_hashes: set[str]) -> pd.DataFrame:
    """构造重复组内保留图到重复图的 pair relation。"""
    created_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    for content_hash in sorted(duplicate_hashes):
        group = frame[frame["content_hash"] == content_hash]["image_id"].tolist()
        if len(group) < 2:
            continue
        keeper = group[0]
        group_id = f"exact-{content_hash}"
        for duplicate in group[1:]:
            rows.append(
                {
                    "relation_type": "exact_duplicate",
                    "source_image_id": keeper,
                    "target_image_id": duplicate,
                    "score": 1.0,
                    "group_id": group_id,
                    "parameter_name": "exact_duplicate_group_id",
                    "computer_name": "duplicate_group_computer",
                    "artifact_ref": "",
                    "created_at": created_at,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "relation_type",
            "source_image_id",
            "target_image_id",
            "score",
            "group_id",
            "parameter_name",
            "computer_name",
            "artifact_ref",
            "created_at",
        ],
    )


def _build_perceptual_groups(
    frame: pd.DataFrame,
    max_distance: int,
) -> tuple[list[dict[str, object]], list[_PerceptualPair]]:
    """按 pHash 与 keeper 的距离构造近重复组。"""
    groups: list[_PerceptualGroup] = []
    assignments: list[_PerceptualAssignment] = []
    pairs: list[_PerceptualPair] = []

    for row in frame.to_dict(orient="records"):
        image_id = str(row["image_id"])
        phash = str(row.get("phash") or "")
        if not phash:
            assignments.append(_PerceptualAssignment(image_id=image_id, group_index=None, distance=None))
            continue

        best_group_index: int | None = None
        best_distance: int | None = None
        for index, group in enumerate(groups):
            distance = _hamming_distance(phash, group.keeper_phash)
            if distance <= max_distance and (best_distance is None or distance < best_distance):
                best_group_index = index
                best_distance = distance

        if best_group_index is None:
            groups.append(_PerceptualGroup(keeper_image_id=image_id, keeper_phash=phash, members=[image_id]))
            assignments.append(_PerceptualAssignment(image_id=image_id, group_index=len(groups) - 1, distance=0))
            continue

        if best_distance is None:
            raise ValueError("best perceptual duplicate distance is missing")
        group = groups[best_group_index]
        group.members.append(image_id)
        assignments.append(
            _PerceptualAssignment(image_id=image_id, group_index=best_group_index, distance=best_distance)
        )
        pairs.append(
            _PerceptualPair(
                source_image_id=group.keeper_image_id,
                target_image_id=image_id,
                distance=best_distance,
                group_id=f"perceptual-{group.keeper_phash}",
            )
        )

    rows: list[dict[str, object]] = []
    for assignment in assignments:
        group_index = assignment.group_index
        if group_index is None:
            rows.append(
                {
                    "image_id": assignment.image_id,
                    "perceptual_duplicate_group_id": "",
                    "perceptual_duplicate_count": 1,
                    "perceptual_duplicate_distance": pd.NA,
                }
            )
            continue
        group = groups[group_index]
        count = len(group.members)
        group_id = f"perceptual-{group.keeper_phash}" if count > 1 else ""
        rows.append(
            {
                "image_id": assignment.image_id,
                "perceptual_duplicate_group_id": group_id,
                "perceptual_duplicate_count": count,
                "perceptual_duplicate_distance": assignment.distance if count > 1 else pd.NA,
            }
        )
    return rows, pairs


def _build_perceptual_duplicate_pairs(pair_rows: list[_PerceptualPair]) -> pd.DataFrame:
    """构造视觉近重复 pair relation。"""
    created_at = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "relation_type": "perceptual_duplicate",
            "source_image_id": pair.source_image_id,
            "target_image_id": pair.target_image_id,
            "score": 1.0 - float(pair.distance) / 64.0,
            "group_id": pair.group_id,
            "parameter_name": "perceptual_duplicate_group_id",
            "computer_name": "perceptual_duplicate_group_computer",
            "artifact_ref": "",
            "created_at": created_at,
        }
        for pair in pair_rows
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "relation_type",
            "source_image_id",
            "target_image_id",
            "score",
            "group_id",
            "parameter_name",
            "computer_name",
            "artifact_ref",
            "created_at",
        ],
    )


def _hamming_distance(left: str, right: str) -> int:
    """计算两个 16 位十六进制 pHash 的 Hamming distance。"""
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")
