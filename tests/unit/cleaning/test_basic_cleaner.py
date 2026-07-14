from pathlib import Path

import pandas as pd

from image_gallery.cleaning import BasicCleaner, CleanerExecution, CleanerResult
from image_gallery.cleaning.events import RuntimeEvent
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry


def _dataset(tmp_path: Path) -> Dataset:
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": ["platform://local/a.jpg", "platform://local/b.jpg"],
                "source_uri": ["file:///a.jpg", "file:///b.jpg"],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_basic_cleaner_compile_returns_execution() -> None:
    cleaner = BasicCleaner([{"decode": {}}])

    execution = cleaner.compile()

    assert isinstance(execution, CleanerExecution)


def test_basic_cleaner_plan_auto_compiles_without_running_dataset(tmp_path: Path) -> None:
    del tmp_path
    cleaner = BasicCleaner([{"decode": {}}])

    frame = cleaner.plan()

    assert "evaluation.decode" in frame["node_id"].tolist()


def test_basic_cleaner_run_returns_result_and_hides_process_outputs(tmp_path: Path) -> None:
    result = BasicCleaner([{"decode": {}}]).run(_dataset(tmp_path), label="unit")

    assert isinstance(result, CleanerResult)
    assert result.status() == "completed"
    assert not (tmp_path / "parameter_table.parquet").exists()


def test_basic_cleaner_exposes_toml_but_not_yaml_config_entrypoint() -> None:
    assert hasattr(BasicCleaner, "from_toml")
    assert not hasattr(BasicCleaner, "from_yaml")


def test_basic_cleaner_run_accepts_progress_callback(tmp_path: Path) -> None:
    events: list[RuntimeEvent] = []

    result = BasicCleaner([{"decode": {}}]).run(
        _dataset(tmp_path),
        progress=events.append,
    )

    assert result.status() == "completed"
    event_types = [event.event_type for event in events]
    assert "run_started" in event_types
    assert "run_completed" in event_types


def test_basic_cleaner_run_auto_progress_prints_notebook_friendly_lines(tmp_path: Path, capsys) -> None:
    result = BasicCleaner([{"decode": {}}]).run(
        _dataset(tmp_path),
        progress="auto",
    )

    captured = capsys.readouterr()

    assert result.status() == "completed"
    assert "[cleaner:" in captured.out
    assert "run_started" in captured.out
    assert "run_completed" in captured.out


def test_basic_cleaner_exposes_builder_lifecycle_only(tmp_path: Path) -> None:
    del tmp_path
    cleaner = BasicCleaner([{"decode": {}}])

    for name in ("preview", "preview_html", "state", "rerun", "result", "export"):
        assert not hasattr(cleaner, name)


def test_basic_cleaner_can_explicitly_override_registered_operator_spec() -> None:
    registry = create_default_registry()
    original = registry.get_operator("blur")
    replacement = type(original)(
        name=original.name,
        category=original.category,
        required_parameters=original.required_parameters,
        evaluation_columns=original.evaluation_columns,
        default_config={**original.default_config, "min_score": 42.0},
        action_column=original.action_column,
        reason_column=original.reason_column,
        evaluator=original.evaluator,
        preview_policy=original.preview_policy,
    )

    execution = BasicCleaner([replacement], registry=registry, override=True).compile()

    assert execution.configured_operators[0].config["min_score"] == 42.0
