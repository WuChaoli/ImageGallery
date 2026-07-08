import pandas as pd

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.tables import CleaningTables, initialize_evaluation_table
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class ScoreComputer(ParameterComputer):
    name = "score_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    threshold = float(config["threshold"])
    failed = parameter_table["score"] >= threshold
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "score_action": failed.map(lambda value: "drop" if value else "keep"),
            "score_reason": failed.map(lambda value: "too high" if value else ""),
        }
    )


def test_operator_evaluator_updates_tables_and_state() -> None:
    registry = OperatorRegistry()
    registry.register_parameter_computer(ScoreComputer())
    registry.register_operator(
        OperatorSpec(
            name="quality.score_check",
            category="quality",
            required_parameters=["score"],
            evaluation_columns=["score_action", "score_reason"],
            default_config={"threshold": 0.5},
            action_column="score_action",
            reason_column="score_reason",
            evaluator=_evaluate,
        )
    )
    compiled = CleaningRunPlanner(registry).compile(parse_operator_configs([{"quality.score_check": {}}]))
    parameter_table = pd.DataFrame({"image_id": ["img-1"], "image_uri": ["a.jpg"], "score": [0.9]})
    tables = CleaningTables(
        parameter_table=parameter_table,
        evaluation_table=initialize_evaluation_table(parameter_table),
        operator_outputs={},
        parameter_manifest={},
    )

    updated_tables, state = OperatorEvaluator().evaluate(compiled.resolved_operator_runs[0], tables)

    assert updated_tables.evaluation_table["score_action"].tolist() == ["drop"]
    assert updated_tables.operator_outputs == {"quality.score_check": ["score_action", "score_reason"]}
    assert state.operator_name == "quality.score_check"
    assert state.parameter_columns == ["score"]
    assert state.evaluation_columns == ["score_action", "score_reason"]
    assert state.processed_count == 1
