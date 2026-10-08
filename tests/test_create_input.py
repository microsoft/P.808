from unittest.mock import Mock

import pandas as pd
import pytest

from src import create_input


ACR_COLUMNS = [
    "rating_clips",
    "math",
    "pair_a",
    "pair_b",
    "trapping_clips",
    "trapping_ans",
]


@pytest.fixture(autouse=True)
def clear_condition_cache():
    """
    Clear the filename-to-condition cache around each test.

    :return: None.
    """
    create_input.file_to_condition_map.clear()
    yield
    create_input.file_to_condition_map.clear()


def test_conv_filename_to_condition_returns_sorted_groups():
    """
    Verify that named condition groups are returned in sorted order.

    :return: None.
    """
    pattern = r"(?P<noise>[^_]+)_(?P<level>\d+)\.wav"

    result = create_input.conv_filename_to_condition("white_10.wav", pattern)

    assert list(result.items()) == [("level", "10"), ("noise", "white")]


def test_conv_filename_to_condition_marks_nonmatching_filename():
    """
    Verify that a filename that does not match is marked as unknown.

    :return: None.
    """
    pattern = r"(?P<noise>[^_]+)_(?P<level>\d+)\.wav"

    result = create_input.conv_filename_to_condition("unexpected.wav", pattern)

    assert result == {"Unknown": "NoCondition"}


def test_validate_inputs_accepts_minimal_acr_columns():
    """
    Verify that the required ACR input columns pass validation.

    :return: None.
    """
    cfg = {"number_of_gold_clips_per_session": "0"}
    data = pd.DataFrame(columns=ACR_COLUMNS)

    create_input.validate_inputs(cfg, data, "acr")


def test_validate_inputs_rejects_missing_required_column():
    """
    Verify that validation identifies a missing required ACR column.

    :return: None.
    """
    cfg = {"number_of_gold_clips_per_session": "0"}
    data = pd.DataFrame(columns=[column for column in ACR_COLUMNS if column != "pair_b"])

    with pytest.raises(AssertionError, match="pair_b"):
        create_input.validate_inputs(cfg, data, "acr")


def test_validate_inputs_requires_gold_columns_when_enabled():
    """
    Verify that enabling gold clips requires their input columns.

    :return: None.
    """
    cfg = {"number_of_gold_clips_per_session": "1"}
    data = pd.DataFrame(columns=ACR_COLUMNS)

    with pytest.raises(AssertionError, match="gold_clips"):
        create_input.validate_inputs(cfg, data, "acr")


def test_create_input_for_mturk_dispatches_acr(monkeypatch):
    """
    Verify that ACR-compatible methods use the ACR input generator.

    :param monkeypatch: Pytest fixture used to replace the input generator.
    :return: None.
    """
    cfg = object()
    data = object()
    output_path = "output.csv"
    create_acr = Mock(return_value=3)
    monkeypatch.setattr(create_input, "create_input_for_acr", create_acr)

    result = create_input.create_input_for_mturk(cfg, data, "p835", output_path)

    assert result == 3
    create_acr.assert_called_once_with(cfg, data, output_path, "p835")


def test_create_input_for_mturk_dispatches_comparison_method(monkeypatch):
    """
    Verify that comparison methods use the DCR/CCR input generator.

    :param monkeypatch: Pytest fixture used to replace the input generator.
    :return: None.
    """
    cfg = object()
    data = object()
    output_path = "output.csv"
    create_comparison = Mock(return_value=2)
    monkeypatch.setattr(create_input, "create_input_for_dcrccr", create_comparison)

    result = create_input.create_input_for_mturk(cfg, data, "ccr", output_path)

    assert result == 2
    create_comparison.assert_called_once_with(cfg, data, output_path)
