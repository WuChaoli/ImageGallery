import pandas as pd

from image_gallery.cleaning.action_range import ActionRange
from image_gallery.cleaning.rule_evaluator import evaluate_with_rules
from image_gallery.operators.metric_spec import MetricSpec


def _make_table(values: list[float | None], column: str = "blur_score") -> pd.DataFrame:
    return pd.DataFrame({"image_id": [f"img_{i}" for i in range(len(values))], column: values})


class TestRelativeMetricEvaluation:
    def test_drop_when_in_drop_range(self) -> None:
        # blur_score: 0-300, relative, higher_better
        # normalized: 60/300 = 0.2, which is in [0, 0.3] → drop
        metric = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        rules = {
            "drop": ActionRange.from_string("[0, 0.3]"),
            "review": ActionRange.from_string("(0.3, 0.6]"),
        }
        table = _make_table([60.0])
        actions = evaluate_with_rules(table, "blur_score", metric, rules)
        assert actions.iloc[0] == "drop"

    def test_review_when_in_review_range(self) -> None:
        # normalized: 135/300 = 0.45, which is in (0.3, 0.6] → review
        metric = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        rules = {
            "drop": ActionRange.from_string("[0, 0.3]"),
            "review": ActionRange.from_string("(0.3, 0.6]"),
        }
        table = _make_table([135.0])
        actions = evaluate_with_rules(table, "blur_score", metric, rules)
        assert actions.iloc[0] == "review"

    def test_keep_when_outside_all_ranges(self) -> None:
        # normalized: 240/300 = 0.8, outside [0, 0.3] and (0.3, 0.6] → keep
        metric = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        rules = {
            "drop": ActionRange.from_string("[0, 0.3]"),
            "review": ActionRange.from_string("(0.3, 0.6]"),
        }
        table = _make_table([240.0])
        actions = evaluate_with_rules(table, "blur_score", metric, rules)
        assert actions.iloc[0] == "keep"


class TestAbsoluteMetricEvaluation:
    def test_drop_when_below_threshold(self) -> None:
        # dimension: absolute, min_width directly checked
        metric = MetricSpec(name="width", value_type="absolute", direction="higher_better")
        rules = {
            "drop": ActionRange.from_string("[0, 256)"),
            "review": ActionRange.from_string("[256, 512)"),
        }
        table = _make_table([200.0], column="width")
        actions = evaluate_with_rules(table, "width", metric, rules)
        assert actions.iloc[0] == "drop"

    def test_review_when_in_review_threshold(self) -> None:
        metric = MetricSpec(name="width", value_type="absolute", direction="higher_better")
        rules = {
            "drop": ActionRange.from_string("[0, 256)"),
            "review": ActionRange.from_string("[256, 512)"),
        }
        table = _make_table([400.0], column="width")
        actions = evaluate_with_rules(table, "width", metric, rules)
        assert actions.iloc[0] == "review"

    def test_keep_when_above_all_thresholds(self) -> None:
        metric = MetricSpec(name="width", value_type="absolute", direction="higher_better")
        rules = {
            "drop": ActionRange.from_string("[0, 256)"),
            "review": ActionRange.from_string("[256, 512)"),
        }
        table = _make_table([1024.0], column="width")
        actions = evaluate_with_rules(table, "width", metric, rules)
        assert actions.iloc[0] == "keep"


class TestDropPriorityOverReview:
    def test_drop_takes_priority_when_both_match(self) -> None:
        # 构造重叠区间：drop [0, 0.5], review [0, 1]
        # 值 0.2 同时命中两个区间，drop 应优先
        metric = MetricSpec(name="score", value_type="absolute", direction="lower_better")
        rules = {
            "drop": ActionRange.from_string("[0, 0.5]"),
            "review": ActionRange.from_string("[0, 1]"),
        }
        table = _make_table([0.2], column="score")
        actions = evaluate_with_rules(table, "score", metric, rules)
        assert actions.iloc[0] == "drop"


class TestBatchEvaluation:
    def test_multiple_rows(self) -> None:
        metric = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        rules = {
            "drop": ActionRange.from_string("[0, 0.3]"),
            "review": ActionRange.from_string("(0.3, 0.6]"),
        }
        # 60 → 0.2 → drop, 135 → 0.45 → review, 240 → 0.8 → keep
        table = _make_table([60.0, 135.0, 240.0])
        actions = evaluate_with_rules(table, "blur_score", metric, rules)
        assert list(actions) == ["drop", "review", "keep"]

    def test_nan_values_get_keep(self) -> None:
        metric = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        rules = {"drop": ActionRange.from_string("[0, 0.3]")}
        table = _make_table([None, 60.0])
        actions = evaluate_with_rules(table, "blur_score", metric, rules)
        assert actions.iloc[0] == "keep"
        assert actions.iloc[1] == "drop"


class TestZeroRangeNormalization:
    def test_abs_range_zero_when_min_equals_max(self) -> None:
        # absolute_min == absolute_max → abs_range == 0 分支
        # normalized = raw_values - abs_min = 5.0 - 5.0 = 0.0
        metric = MetricSpec(
            name="fixed_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=5.0,
            absolute_max=5.0,
        )
        rules = {"drop": ActionRange.from_string("[0, 0.5]")}
        table = _make_table([5.0], column="fixed_score")
        actions = evaluate_with_rules(table, "fixed_score", metric, rules)
        # 0.0 in [0, 0.5] → drop
        assert actions.iloc[0] == "drop"

    def test_abs_range_zero_value_outside_drop(self) -> None:
        # normalized = 6.0 - 5.0 = 1.0，不在 [0, 0.5] → keep
        metric = MetricSpec(
            name="fixed_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=5.0,
            absolute_max=5.0,
        )
        rules = {"drop": ActionRange.from_string("[0, 0.5]")}
        table = _make_table([6.0], column="fixed_score")
        actions = evaluate_with_rules(table, "fixed_score", metric, rules)
        assert actions.iloc[0] == "keep"


class TestSingleRuleEvaluation:
    def test_only_drop_rule(self) -> None:
        # 仅传 drop 规则，不传 review
        metric = MetricSpec(name="score", value_type="absolute", direction="lower_better")
        rules = {"drop": ActionRange.from_string("[0, 0.3]")}
        table = _make_table([0.1, 0.5], column="score")
        actions = evaluate_with_rules(table, "score", metric, rules)
        assert list(actions) == ["drop", "keep"]

    def test_only_review_rule(self) -> None:
        # 仅传 review 规则，不传 drop
        metric = MetricSpec(name="score", value_type="absolute", direction="lower_better")
        rules = {"review": ActionRange.from_string("[0.3, 0.6]")}
        table = _make_table([0.1, 0.5, 0.8], column="score")
        actions = evaluate_with_rules(table, "score", metric, rules)
        assert list(actions) == ["keep", "review", "keep"]
