import pytest

from image_gallery.cleaning.action_range import ActionRange


class TestFromString:
    def test_closed_interval(self) -> None:
        ar = ActionRange.from_string("[0, 0.3]")
        assert ar.lower == 0.0
        assert ar.upper == 0.3
        assert ar.lower_inclusive is True
        assert ar.upper_inclusive is True

    def test_open_interval(self) -> None:
        ar = ActionRange.from_string("(0.3, 0.6)")
        assert ar.lower == 0.3
        assert ar.upper == 0.6
        assert ar.lower_inclusive is False
        assert ar.upper_inclusive is False

    def test_left_open_right_closed(self) -> None:
        ar = ActionRange.from_string("(0.3, 0.6]")
        assert ar.lower == 0.3
        assert ar.upper == 0.6
        assert ar.lower_inclusive is False
        assert ar.upper_inclusive is True

    def test_left_closed_right_open(self) -> None:
        ar = ActionRange.from_string("[0.3, 0.6)")
        assert ar.lower == 0.3
        assert ar.upper == 0.6
        assert ar.lower_inclusive is True
        assert ar.upper_inclusive is False

    def test_negative_values(self) -> None:
        ar = ActionRange.from_string("[-1.5, 2.5]")
        assert ar.lower == -1.5
        assert ar.upper == 2.5

    def test_whitespace_tolerance(self) -> None:
        ar = ActionRange.from_string("  [ 0 , 1 ]  ")
        assert ar.lower == 0.0
        assert ar.upper == 1.0


class TestFromStringInvalid:
    def test_missing_brackets(self) -> None:
        with pytest.raises(ValueError, match="invalid interval syntax"):
            ActionRange.from_string("0.3, 0.6")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="invalid interval syntax"):
            ActionRange.from_string("")

    def test_only_one_value(self) -> None:
        with pytest.raises(ValueError, match="invalid interval syntax"):
            ActionRange.from_string("[0.3]")

    def test_infinity_lower(self) -> None:
        with pytest.raises(ValueError, match="invalid interval syntax"):
            ActionRange.from_string("[-inf, 0.3]")

    def test_infinity_upper(self) -> None:
        with pytest.raises(ValueError, match="invalid interval syntax"):
            ActionRange.from_string("[0.3, inf]")


class TestContains:
    def test_closed_interval_contains_boundary(self) -> None:
        ar = ActionRange.from_string("[0, 0.3]")
        assert ar.contains(0.0) is True
        assert ar.contains(0.3) is True
        assert ar.contains(0.15) is True

    def test_closed_interval_excludes_outside(self) -> None:
        ar = ActionRange.from_string("[0, 0.3]")
        assert ar.contains(-0.1) is False
        assert ar.contains(0.4) is False

    def test_open_interval_excludes_boundary(self) -> None:
        ar = ActionRange.from_string("(0, 1)")
        assert ar.contains(0.0) is False
        assert ar.contains(1.0) is False
        assert ar.contains(0.5) is True

    def test_left_open_right_closed(self) -> None:
        ar = ActionRange.from_string("(0.3, 0.6]")
        assert ar.contains(0.3) is False
        assert ar.contains(0.6) is True
        assert ar.contains(0.45) is True

    def test_left_closed_right_open(self) -> None:
        ar = ActionRange.from_string("[0.3, 0.6)")
        assert ar.contains(0.3) is True
        assert ar.contains(0.6) is False
        assert ar.contains(0.45) is True
