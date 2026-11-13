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

COMPARISON_CONDITIONS = [f"C{index:02d}" for index in range(1, 11)]
COMPARISON_SOURCES = [f"S{index:02d}" for index in range(1, 5)]


def _create_comparison_input_data():
    """
    Create a minimal dataframe for DCR/CCR input-generation tests.

    :return: Tuple containing the dataframe, rating clips, and references.
    """
    clips = [
        f"{source}_{condition}.wav"
        for source in COMPARISON_SOURCES
        for condition in COMPARISON_CONDITIONS
    ]
    references = [
        f"reference-{source}.wav"
        for source in COMPARISON_SOURCES
        for _ in COMPARISON_CONDITIONS
    ]
    clip_count = len(clips)
    data = pd.DataFrame(
        {
            "rating_clips": clips,
            "references": references,
            "math": ["math.wav"] * clip_count,
            "pair_a": [f"pair-a-{index}.wav" for index in range(clip_count)],
            "pair_b": [f"pair-b-{index}.wav" for index in range(clip_count)],
            "trapping_clips": [None] * clip_count,
        }
    )
    return data, clips, references


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


def test_prepacked_ccr_preserves_assignments_and_bandwidth_sets(tmp_path):
    """
    Retain preassigned identities/orders and synchronize every bandwidth-set field.

    :param tmp_path: Temporary CSV directory.
    :return: None.
    """
    data, _, _ = _create_comparison_input_data()
    for index in range(1, 6):
        data[f"comb_bw{index}"] = f"bandwidth-{index}.wav"
        data[f"ans_comb_bw{index}"] = "sq"
        data[f"comb_bw_hash{index}"] = f"hash-{index}"
    prepacked = pd.DataFrame({
        "bundle_id": ["bundle-1", "bundle-2"],
        "Q0_R": ["a.wav", "c.wav"], "Q0_P": ["b.wav", "d.wav"],
        "Q0_ID": ["ab", "cd"], "Q0_ORDER": ["ba", "ab"],
    })
    source = tmp_path / "prepacked.csv"
    prepacked.to_csv(source, index=False)
    output = tmp_path / "output.csv"
    count = create_input.create_input_for_dcrccr({
        "clip_packing_strategy": "prepacked", "prepacked_sessions": str(source),
        "number_of_clips_per_session": "1", "number_of_trapping_per_session": "0",
    }, data, str(output))
    result = pd.read_csv(output)
    assert count == 2
    pd.testing.assert_frame_equal(result[prepacked.columns], prepacked)
    assert "TP" not in result
    for index in range(1, 6):
        assert result[f"comb_bw{index}"].tolist() == [f"bandwidth-{index}.wav"] * 2
        assert result[f"comb_bw_hash{index}"].tolist() == [f"hash-{index}"] * 2


@pytest.mark.parametrize("case", ["missing_column", "empty_url", "bad_order", "input_collision"])
def test_prepacked_ccr_rejects_unusable_assignments(tmp_path, case):
    """
    Reject ambiguous or destructive prepacked input before writing output.

    :param tmp_path: Temporary CSV directory.
    :param case: Input-integrity failure to exercise.
    :return: None.
    """
    data, _, _ = _create_comparison_input_data()
    row = {"Q0_R": "a.wav", "Q0_P": "b.wav", "Q0_ORDER": "ab"}
    if case == "missing_column":
        del row["Q0_R"]
    elif case == "empty_url":
        row["Q0_P"] = " "
    elif case == "bad_order":
        row["Q0_ORDER"] = "random"
    source = tmp_path / "prepacked.csv"
    pd.DataFrame([row]).to_csv(source, index=False)
    output = source if case == "input_collision" else tmp_path / "output.csv"
    before = source.read_bytes()
    with pytest.raises(ValueError):
        create_input.create_input_for_dcrccr({
            "clip_packing_strategy": "prepacked", "prepacked_sessions": str(source),
            "number_of_clips_per_session": "1", "number_of_trapping_per_session": "0",
        }, data, str(output))
    assert source.read_bytes() == before


def test_create_input_for_mturk_preserves_balanced_ccr_blocks(tmp_path, monkeypatch):
    """
    Verify that CCR generation preserves balanced blocks and reference pairing.

    :param tmp_path: Pytest-provided temporary output directory.
    :param monkeypatch: Pytest fixture used to make list shuffling deterministic.
    :return: None.
    """
    data, clips, references = _create_comparison_input_data()
    cfg = {
        "number_of_clips_per_session": "10",
        "number_of_trapping_per_session": "0",
        "clip_packing_strategy": "balanced_block",
        "condition_pattern": r"(?P<source>S\d{2})_(?P<condition>C\d{2})\.wav",
        "block_keys": "condition, source",
    }
    output_path = tmp_path / "balanced.csv"
    monkeypatch.setattr(create_input.random, "shuffle", Mock())

    session_count = create_input.create_input_for_mturk(cfg, data, "ccr", output_path)
    output = pd.read_csv(output_path)
    reference_by_clip = dict(zip(clips, references))

    assert session_count == 4
    assert len(output) == 4
    observed_sources = set()
    for _, row in output.iterrows():
        presented_clips = [row[f"Q{index}_P"] for index in range(10)]
        presented_conditions = {clip.split("_")[1].removesuffix(".wav") for clip in presented_clips}
        presented_sources = {clip.split("_")[0] for clip in presented_clips}
        assert presented_conditions == set(COMPARISON_CONDITIONS)
        assert len(presented_sources) == 1
        observed_sources.update(presented_sources)
        for index, clip in enumerate(presented_clips):
            assert row[f"Q{index}_R"] == reference_by_clip[clip]
    assert observed_sources == set(COMPARISON_SOURCES)


def test_create_input_for_mturk_preserves_random_ccr_reference_pairs(tmp_path, monkeypatch):
    """
    Verify that random CCR generation retains each processed/reference pair.

    :param tmp_path: Pytest-provided temporary output directory.
    :param monkeypatch: Pytest fixture used to make list shuffling deterministic.
    :return: None.
    """
    data, clips, references = _create_comparison_input_data()
    cfg = {
        "number_of_clips_per_session": "10",
        "number_of_trapping_per_session": "0",
        "clip_packing_strategy": "random",
    }
    output_path = tmp_path / "random.csv"
    seeded_random = create_input.random.Random(5)
    monkeypatch.setattr(create_input.random, "shuffle", seeded_random.shuffle)

    session_count = create_input.create_input_for_mturk(cfg, data, "ccr", output_path)
    output = pd.read_csv(output_path)
    reference_by_clip = dict(zip(clips, references))

    assert session_count == 4
    assert len(output) == 4
    unique_condition_counts = []
    for _, row in output.iterrows():
        presented_clips = [row[f"Q{index}_P"] for index in range(10)]
        presented_conditions = {clip.split("_")[1].removesuffix(".wav") for clip in presented_clips}
        unique_condition_counts.append(len(presented_conditions))
        for index, clip in enumerate(presented_clips):
            assert row[f"Q{index}_R"] == reference_by_clip[clip]
    assert any(count < len(COMPARISON_CONDITIONS) for count in unique_condition_counts)
