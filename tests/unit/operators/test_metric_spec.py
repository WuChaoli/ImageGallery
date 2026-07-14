import pytest

from image_gallery.operators.builtin import create_default_metric_specs
from image_gallery.operators.metric_spec import MetricSpec, relative_to_absolute


class TestMetricSpec:
    def test_absolute_type(self) -> None:
        spec = MetricSpec(name="min_width", value_type="absolute", direction="higher_better")
        assert spec.value_type == "absolute"
        assert spec.absolute_min is None
        assert spec.absolute_max is None

    def test_relative_type(self) -> None:
        spec = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        assert spec.value_type == "relative"
        assert spec.absolute_min == 0.0
        assert spec.absolute_max == 300.0

    def test_categorical_type(self) -> None:
        spec = MetricSpec(name="decode_ok", value_type="categorical", direction="categorical")
        assert spec.value_type == "categorical"
        assert spec.direction == "categorical"


class TestRelativeToAbsolute:
    def test_midpoint_mapping(self) -> None:
        spec = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        assert relative_to_absolute(spec, 0.5) == 150.0

    def test_zero_mapping(self) -> None:
        spec = MetricSpec(
            name="noise_score",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        )
        assert relative_to_absolute(spec, 0.0) == 0.0

    def test_one_mapping(self) -> None:
        spec = MetricSpec(
            name="noise_score",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        )
        assert relative_to_absolute(spec, 1.0) == 1.0

    def test_out_of_range_raises(self) -> None:
        spec = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        with pytest.raises(ValueError, match="out of \\[0, 1\\] range"):
            relative_to_absolute(spec, 1.1)

    def test_negative_out_of_range_raises(self) -> None:
        spec = MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        )
        with pytest.raises(ValueError, match="out of \\[0, 1\\] range"):
            relative_to_absolute(spec, -0.1)

    def test_absolute_type_raises(self) -> None:
        spec = MetricSpec(name="min_width", value_type="absolute", direction="higher_better")
        with pytest.raises(TypeError, match="value_type='relative'"):
            relative_to_absolute(spec, 0.5)

    def test_categorical_type_raises(self) -> None:
        spec = MetricSpec(name="decode_ok", value_type="categorical", direction="categorical")
        with pytest.raises(TypeError, match="value_type='relative'"):
            relative_to_absolute(spec, 0.5)

    def test_missing_absolute_range_raises(self) -> None:
        spec = MetricSpec(name="broken", value_type="relative", direction="higher_better")
        with pytest.raises(ValueError, match="missing absolute_min/absolute_max"):
            relative_to_absolute(spec, 0.5)


class TestCreateDefaultMetricSpecs:
    def test_returns_17_entries(self) -> None:
        specs = create_default_metric_specs()
        assert len(specs) == 17

    def test_blur_is_relative(self) -> None:
        specs = create_default_metric_specs()
        blur = specs["blur"]
        assert blur.value_type == "relative"
        assert blur.absolute_min == 0.0
        assert blur.absolute_max == 300.0

    def test_dimension_is_absolute(self) -> None:
        specs = create_default_metric_specs()
        dim = specs["dimension"]
        assert dim.value_type == "absolute"

    def test_decode_is_categorical(self) -> None:
        specs = create_default_metric_specs()
        decode = specs["decode"]
        assert decode.value_type == "categorical"
