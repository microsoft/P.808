import pytest
import os
import sys
sys.path.insert(0, os.path.abspath("src"))
import pandas as pd
from configparser import ConfigParser
import create_input


def _basic_cfg():
    cfg = ConfigParser()
    cfg['general'] = {
        'number_of_clips_per_session': '2',
        'number_of_trapping_per_session': '1',
        'number_of_gold_clips_per_session': '0',
        'clip_packing_strategy': 'random'
    }
    return cfg


def _row_input():
    data = {
        'rating_clips': ['a.wav', 'b.wav'],
        'math': ['math1.wav', 'math2.wav'],
        'pair_a': ['pa1', 'pa2'],
        'pair_b': ['pb1', 'pb2'],
        'trapping_clips': ['trap1.wav', 'trap2.wav'],
        'trapping_ans': [1, 2]
    }
    return pd.DataFrame(data)


def test_validate_inputs_success():
    cfg = _basic_cfg()
    df = _row_input()
    # should not raise
    create_input.validate_inputs(cfg['general'], df, 'acr')


def test_validate_inputs_missing_column():
    cfg = _basic_cfg()
    df = _row_input().drop(columns=['pair_b'])
    with pytest.raises(AssertionError):
        create_input.validate_inputs(cfg['general'], df, 'acr')


def test_create_input_for_mturk(tmp_path):
    cfg = _basic_cfg()
    df = _row_input()
    output_file = tmp_path / 'out.csv'
    n_sessions = create_input.create_input_for_mturk(cfg['general'], df, 'acr', str(output_file))
    assert n_sessions == 1
    assert output_file.exists()
    out_df = pd.read_csv(output_file)
    # should contain Q0 and Q1 columns for two clips
    assert 'Q0' in out_df.columns and 'Q1' in out_df.columns


def test_conv_filename_to_condition():
    pattern = r".*_c(?P<condition_num>\d{1,2})_.*\.wav"
    result = create_input.conv_filename_to_condition('D501_c03_M2_S02.wav', pattern)
    assert result['condition_num'] == '03'

