from datetime import datetime, timezone

import pandas as pd

from image_gallery.operators.computers.base import ComputeStage, ParameterComputer, ParameterRequest, ParameterResult


class DuplicateGroupComputer(ParameterComputer):
    """基于 content_hash 生产完全重复分组。"""

    name = "duplicate_group_computer"
    stage = ComputeStage.DATASET_GLOBAL
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
                    "stage": self.stage.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["content_hash"],
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
