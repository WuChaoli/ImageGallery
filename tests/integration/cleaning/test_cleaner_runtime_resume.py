import json
import sqlite3
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.operators.builtin import evaluate_perceptual_duplicate_check
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.computers.duplicate import PerceptualDuplicateGroupComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def _write_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color=color).save(path)


def _tiny_dataset(tmp_path: Path) -> object:
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    _write_image(first, size=(16, 16), color=(255, 0, 0))
    _write_image(second, size=(4, 4), color=(0, 255, 0))
    return pd.DataFrame(
        {
            "image_id": ["img-1", "img-2"],
            "image_uri": [str(first), str(second)],
        }
    )


def _write_dataset(tmp_path: Path, name: str, frame: pd.DataFrame):
    from image_gallery.dataset import Dataset

    return Dataset.write(frame, str(tmp_path / name))


def _always_keep(frame: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    del config
    return pd.DataFrame(
        {
            "image_id": frame["image_id"],
            "counted_action": ["keep"] * len(frame),
            "counted_reason": [""] * len(frame),
        }
    )


class CountingArtifactComputer(ParameterComputer):
    """测试用计数 computer，用于验证 resume 不会重复执行已完成节点。"""

    name = "counting_artifact_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"counted_parameter"})
    call_count: ClassVar[int] = 0

    @classmethod
    def reset(cls) -> None:
        cls.call_count = 0

    def compute(self, request: ParameterRequest) -> ParameterResult:
        type(self).call_count += 1
        artifact_dir = request.artifacts_dir / "counted_parameter"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "value.txt").write_text(str(type(self).call_count), encoding="utf-8")
        (artifact_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "artifact_schema_version": 1,
                    "computer": self.name,
                    "config_hash": request.config_hash,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "counted_parameter": ["ready"] * len(request.parameter_table),
                }
            ),
            relation_updates={},
            artifact_refs={"counted_parameter": str(artifact_dir)},
            parameter_manifest={
                "counted_parameter": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "artifact_ref": str(artifact_dir),
                }
            },
        )


def _counting_registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(CountingArtifactComputer())
    registry.register_operator(
        OperatorSpec(
            name="test.counted_check",
            category="test",
            required_parameters=["counted_parameter"],
            evaluation_columns=["counted_action", "counted_reason"],
            default_config={"action": "keep"},
            action_column="counted_action",
            reason_column="counted_reason",
            evaluator=_always_keep,
        )
    )
    return registry


def _mark_run_as_partial(run_dir: Path, run_id: str) -> None:
    connection = sqlite3.connect(run_dir / "run_state.sqlite")
    try:
        connection.execute("UPDATE cleaning_run SET status = ? WHERE run_id = ?", ("running", run_id))
        connection.execute(
            "UPDATE graph_node SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE run_id = ? AND node_id = ?",
            ("completed", run_id, "parameter.counting_artifact_computer"),
        )
        connection.execute(
            "UPDATE graph_node SET status = ?, finished_at = NULL WHERE run_id = ? AND node_id != ?",
            ("pending", run_id, "parameter.counting_artifact_computer"),
        )
        connection.commit()
    finally:
        connection.close()

    state_path = run_dir / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["status"] = "running"
    payload["finished_at"] = ""
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class FixedPerceptualHashComputer(ParameterComputer):
    """测试用固定 pHash 生产器。"""

    name = "fixed_perceptual_hash_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"phash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "phash": ["0000000000000000", "0000000000000001"],
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "phash": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def _perceptual_duplicate_registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(FixedPerceptualHashComputer())
    registry.register_parameter_computer(PerceptualDuplicateGroupComputer())
    registry.register_operator(
        OperatorSpec(
            name="duplicate.perceptual_duplicate_check",
            category="duplicate",
            required_parameters=[
                "perceptual_duplicate_group_id",
                "perceptual_duplicate_count",
                "perceptual_duplicate_distance",
            ],
            evaluation_columns=[
                "perceptual_duplicate_group_id",
                "perceptual_duplicate_count",
                "perceptual_duplicate_distance",
                "perceptual_duplicate_action",
                "perceptual_duplicate_reason",
            ],
            default_config={"max_distance": 10, "keep": "first", "action": "drop"},
            action_column="perceptual_duplicate_action",
            reason_column="perceptual_duplicate_reason",
            evaluator=evaluate_perceptual_duplicate_check,
        )
    )
    return registry


@pytest.mark.parametrize("resume_mode", ["run_id", "result"])
def test_resume_reuses_completed_run_by_run_id_or_result(tmp_path: Path, resume_mode: str) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    execution = BasicCleaner([{"format.decode_check": {}}], output_dir=tmp_path / "cleaning").compile()
    result = execution.run(dataset)
    before = result.export("full", tmp_path / "before.parquet").to_frame()

    if resume_mode == "run_id":
        resumed = execution.resume(dataset=dataset, run_id=result.run_id)
    else:
        resumed = execution.resume(dataset=dataset, result=result)
    after = resumed.export("full", tmp_path / "after.parquet").to_frame()

    assert resumed.run_id == result.run_id
    assert resumed.status() == "completed"
    pd.testing.assert_frame_equal(before, after)


def test_resume_rejects_dataset_fingerprint_mismatch(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    other_dataset = _write_dataset(
        tmp_path,
        "other.parquet",
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": [str(tmp_path / "one.png"), str(tmp_path / "two.png"), str(tmp_path / "one.png")],
            }
        ),
    )
    execution = BasicCleaner([{"format.decode_check": {}}], output_dir=tmp_path / "cleaning").compile()
    result = execution.run(dataset)

    with pytest.raises(ValueError, match="dataset fingerprint"):
        execution.resume(dataset=other_dataset, run_id=result.run_id)


def test_resume_rejects_plan_hash_mismatch(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    first_execution = BasicCleaner([{"format.decode_check": {}}], output_dir=tmp_path / "cleaning").compile()
    result = first_execution.run(dataset)
    second_execution = BasicCleaner(
        [{"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}}],
        output_dir=tmp_path / "cleaning",
    ).compile()

    with pytest.raises(ValueError, match="plan hash"):
        second_execution.resume(dataset=dataset, run_id=result.run_id)


def test_resume_rejects_sample_rule_mismatch(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    execution = BasicCleaner([{"format.decode_check": {}}], output_dir=tmp_path / "cleaning").compile()
    result = execution.run(dataset, sample={"n": 1, "random_state": 1})

    with pytest.raises(ValueError, match="sample rule"):
        execution.resume(dataset=dataset, run_id=result.run_id, sample={"n": 1, "random_state": 2})


def test_rerun_allows_evaluation_only_change(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    execution = BasicCleaner(
        [{"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}}],
        output_dir=tmp_path / "cleaning",
    ).compile()
    result = execution.run(dataset)
    before_parameters = result.export("parameters", tmp_path / "parameters-before.parquet").to_frame()
    before_full = result.export("full", tmp_path / "full-before.parquet").to_frame().set_index("image_id")

    rerun_result = execution.rerun(
        result,
        operators=[{"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}}],
    )
    after_parameters = rerun_result.export("parameters", tmp_path / "parameters-after.parquet").to_frame()
    after_full = rerun_result.export("full", tmp_path / "full-after.parquet").to_frame().set_index("image_id")

    pd.testing.assert_frame_equal(before_parameters, after_parameters)
    assert before_full.loc["img-2", "dimension_action"] == "review"
    assert after_full.loc["img-2", "dimension_action"] == "keep"
    assert rerun_result.run_id == result.run_id
    assert rerun_result.status() == "completed"


def test_rerun_rejects_parameter_computer_config_change(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    execution = BasicCleaner(
        [{"duplicate.perceptual_duplicate_check": {"max_distance": 0}}],
        output_dir=tmp_path / "cleaning",
        registry=_perceptual_duplicate_registry(),
    ).compile()
    result = execution.run(dataset)

    with pytest.raises(ValueError, match="parameter computer config"):
        execution.rerun(result, operators=[{"duplicate.perceptual_duplicate_check": {"max_distance": 1}}])


def test_resume_reuses_completed_parameter_node_for_unfinished_run(tmp_path: Path) -> None:
    CountingArtifactComputer.reset()
    dataset = _write_dataset(tmp_path, "raw.parquet", _tiny_dataset(tmp_path))
    execution = BasicCleaner(
        [{"test.counted_check": {}}],
        output_dir=tmp_path / "cleaning",
        registry=_counting_registry(),
    ).compile()
    result = execution.run(dataset)
    run_dir = (tmp_path / "cleaning") / result.run_id
    _mark_run_as_partial(run_dir, result.run_id)
    before_resume_calls = CountingArtifactComputer.call_count

    resumed = execution.resume(dataset=dataset, run_id=result.run_id)

    assert resumed.status() == "completed"
    assert resumed.run_id == result.run_id
    assert CountingArtifactComputer.call_count == before_resume_calls
