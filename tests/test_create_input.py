import pandas as pd
import pytest

from src.create_input import conv_filename_to_condition, validate_inputs


def test_conv_filename_to_condition_match():
    pattern = r"(?P<noise>[^_]+)_(?P<level>\d+)\.wav"
    result = conv_filename_to_condition("white_10.wav", pattern)
    assert list(result.items()) == [("level", "10"), ("noise", "white")]


def test_conv_filename_to_condition_no_match():
    pattern = r"(?P<noise>[^_]+)_(?P<level>\d+)\.wav"
    result = conv_filename_to_condition("unexpected.wav", pattern)
    assert result == {"Unknown": "NoCondition"}


def test_validate_inputs_acr_minimal():
    cfg = {"number_of_gold_clips_per_session": "0"}
    df = pd.DataFrame(columns=[
        "rating_clips", "math", "pair_a", "pair_b", "trapping_clips", "trapping_ans"
    ])
    validate_inputs(cfg, df, "acr")


def test_validate_inputs_missing_column():
    cfg = {"number_of_gold_clips_per_session": "0"}
    df = pd.DataFrame(columns=[
        "rating_clips", "math", "pair_a", "trapping_clips", "trapping_ans"
    ])
    with pytest.raises(AssertionError):
        validate_inputs(cfg, df, "acr")
