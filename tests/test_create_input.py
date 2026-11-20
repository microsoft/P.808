import hashlib
import random
from collections import Counter
from unittest.mock import Mock

import numpy as np
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
            "pair_ans": [f"pair-b-{index}.wav" for index in range(clip_count)],
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
    Retain preassigned identities/orders, including one comparison shown in both orders, and synchronize every
    bandwidth-set field.

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
        "Q0_R": ["a.wav", "a.wav"], "Q0_P": ["b.wav", "b.wav"],
        "Q0_ID": ["ab", "ab"], "Q0_ORDER": ["ba", "ab"], "Q0_EXPOSURE": ["same_scene", "same_scene"],
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


@pytest.mark.parametrize("case", [
    "missing_column", "empty_url", "bad_order", "empty_id", "unsafe_id", "unsafe_exposure",
    "bad_role", "conflicting_id", "input_collision", "input_symlink_collision",
])
def test_prepacked_ccr_rejects_unusable_assignments(tmp_path, case):
    """
    Reject ambiguous or destructive prepacked input before writing output.

    :param tmp_path: Temporary CSV directory.
    :param case: Input-integrity failure to exercise.
    :return: None.
    """
    data, _, _ = _create_comparison_input_data()
    row = {
        "Q0_R": "a.wav", "Q0_P": "b.wav", "Q0_ORDER": "ab", "Q0_ID": "pair-1",
        "Q0_ROLE": "main", "Q0_EXPOSURE": "same_scene",
    }
    rows = [row]
    if case == "missing_column":
        del row["Q0_R"]
    elif case == "empty_url":
        row["Q0_P"] = " "
    elif case == "bad_order":
        row["Q0_ORDER"] = "random"
    elif case == "empty_id":
        row["Q0_ID"] = " "
    elif case == "unsafe_id":
        row["Q0_ID"] = "pair'1"
    elif case == "unsafe_exposure":
        row["Q0_EXPOSURE"] = "same scene"
    elif case == "bad_role":
        row["Q0_ROLE"] = "trap"
    elif case == "conflicting_id":
        rows.append({**row, "Q0_P": "c.wav", "Q0_ORDER": "ba"})
    source = tmp_path / "prepacked.csv"
    pd.DataFrame(rows).to_csv(source, index=False)
    output = source if case == "input_collision" else tmp_path / "output.csv"
    if case == "input_symlink_collision":
        try:
            output.symlink_to(source)
        except OSError as error:
            pytest.skip(f"Cannot create symlink on this platform: {error}")
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


def _session_items(output_df, n_clips_per_session, comparison):
    """
    Read the packed items of each session from a generated dataframe.

    :param output_df: Dataframe filled by a packing function.
    :param n_clips_per_session: Number of items in each session.
    :param comparison: Whether sessions hold ``(processed, reference)`` pairs instead of single clips.
    :return: List with one list of items per session.
    """
    if comparison:
        return [[(row[f"Q{q}_P"], row[f"Q{q}_R"]) for q in range(n_clips_per_session)]
                for _, row in output_df.iterrows()]
    return [[row[f"Q{q}"] for q in range(n_clips_per_session)] for _, row in output_df.iterrows()]


@pytest.mark.parametrize("comparison", [True, False], ids=["ccr", "acr"])
@pytest.mark.parametrize("repeated", [False, True], ids=["padding_only", "repeated_input"])
def test_random_packing_never_repeats_within_session(monkeypatch, capsys, comparison, repeated):
    """
    Verify that random packing keeps repeats, padding, and reversed pairs out of a session.

    :param monkeypatch: Pytest fixture used to seed the packer.
    :param capsys: Captured generator messages.
    :param comparison: Whether the CCR packer or the ACR packer is tested.
    :param repeated: Whether the input already includes repeated identities.
    :return: None.
    """
    if comparison:
        listed = [(f"p{index}.wav", f"r{index}.wav") for index in range(13)]
        if repeated:
            listed = listed * 3 + [("r0.wav", "p0.wav")]
        n_clips_per_session = 7
    else:
        listed = [f"c{index}.wav" for index in range(9)] * (3 if repeated else 1)
        n_clips_per_session = 4
    n_sessions = -(-len(listed) // n_clips_per_session)
    for seed in range(20):
        monkeypatch.setattr(create_input, "random", random.Random(seed))
        output_df = pd.DataFrame()
        if comparison:
            processed, references = zip(*listed)
            create_input.add_clips_random_ccr(pd.Series(processed), pd.Series(references), n_clips_per_session,
                                              output_df)
        else:
            create_input.add_clips_random(pd.DataFrame({"rating_clips": listed}), n_clips_per_session, output_df,
                                          "acr", ["rating_clips"])
        sessions = _session_items(output_df, n_clips_per_session, comparison)

        assert len(sessions) == n_sessions
        for session in sessions:
            identities = [frozenset(item) if comparison else item for item in session]
            assert len(set(identities)) == n_clips_per_session
        actual = Counter(item for session in sessions for item in session)
        assert not (Counter(listed) - actual)
        assert set(actual) == set(listed)
        assert actual.total() == n_sessions * n_clips_per_session
        assert "WARNING:" not in capsys.readouterr().out


@pytest.mark.parametrize("comparison", [True, False], ids=["ccr", "acr"])
def test_random_padding_uses_an_item_with_remaining_capacity(comparison):
    """
    Pack A,A,B into two A,B sessions instead of padding with a third A and rejecting it.

    :param comparison: Whether the CCR packer or the ACR packer is tested.
    :return: None.
    """
    output = pd.DataFrame()
    if comparison:
        create_input.add_clips_random_ccr(pd.Series(["A", "A", "B"]), pd.Series(["R"] * 3), 2, output)
        expected = Counter({("A", "R"): 2, ("B", "R"): 2})
    else:
        create_input.add_clips_random(pd.DataFrame({"rating_clips": ["A", "A", "B"]}), 2, output,
                                      "acr", ["rating_clips"])
        expected = Counter({"A": 2, "B": 2})
    sessions = _session_items(output, 2, comparison)
    assert len(sessions) == 2
    assert all(len(set(session)) == 2 for session in sessions)
    assert Counter(item for session in sessions for item in session) == expected


@pytest.mark.parametrize("comparison", [True, False], ids=["ccr", "acr"])
@pytest.mark.parametrize("indices", [list(range(5)), [0] * 4 + list(range(1, 21))],
                         ids=["too_few_unique", "too_many_copies"])
def test_random_packing_warns_and_preserves_input_when_repeats_are_unavoidable(capsys, comparison, indices):
    """
    Produce complete sessions and a warning when a session has to repeat an item.

    :param capsys: Captured generator messages.
    :param comparison: Whether the CCR packer or the ACR packer is tested.
    :param indices: Item indices with either insufficient diversity or excessive repetition.
    :return: None.
    """
    output = pd.DataFrame()
    if comparison:
        listed = [(f"p{index}.wav", f"r{index}.wav") for index in indices]
        create_input.add_clips_random_ccr(pd.Series([pair[0] for pair in listed]),
                                          pd.Series([pair[1] for pair in listed]), 10, output)
    else:
        listed = [f"c{index}.wav" for index in indices]
        create_input.add_clips_random(pd.DataFrame({"rating_clips": listed}), 10, output, "acr", ["rating_clips"])
    sessions = _session_items(output, 10, comparison)
    assert len(sessions) == -(-len(listed) // 10)
    assert all(len(session) == 10 for session in sessions)
    assert any(len(set(session)) < 10 for session in sessions)
    actual = Counter(item for session in sessions for item in session)
    assert not (Counter(listed) - actual)
    assert set(actual) == set(listed)
    warning = capsys.readouterr().out
    assert "WARNING: random packing cannot avoid repeated" in warning
    assert "Continuing with repetitions within sessions." in warning


def test_random_packing_still_rejects_empty_input():
    """
    Reject absent data rather than warning and attempting to pad an empty list.

    :return: None.
    """
    with pytest.raises(ValueError, match="At least one comparison is required"):
        create_input.add_clips_random_ccr(pd.Series([], dtype=str), pd.Series([], dtype=str), 10, pd.DataFrame())


def test_assign_cmp_answers_uses_correct_clip_per_pair():
    """
    Keep offline answer slots and browser hashes tied to each CMP pair.

    :return: None.
    """
    pairs = pd.DataFrame(
        {
            "pair_a": ["A.wav", "B.wav", "30_clean.wav", "D.wav"],
            "pair_b": ["B.wav", "C.wav", "10_noisy.wav", "A.wav"],
            "pair_ans": ["B.wav", "C.wav", None, "A.wav"],
        }
    )
    displayed_pairs = np.array(
        [["A.wav", "B.wav", "B.wav", "C.wav", "30_clean.wav", "10_noisy.wav", "D.wav", "A.wav"]]
    )
    output = pd.DataFrame(index=[0])

    create_input._assign_cmp_answers(pairs, output, displayed_pairs)

    assert output.loc[0, ["ans_cmp1", "ans_cmp2", "ans_cmp3", "ans_cmp4"]].tolist() == [
        "b", "b", "a", "b"
    ]
    assert output.loc[0, [
        "cmp_correct_hash1", "cmp_correct_hash2", "cmp_correct_hash3", "cmp_correct_hash4"
    ]].tolist() == [
        hashlib.sha256(url.encode("utf-8")).hexdigest()
        for url in ["B.wav", "C.wav", "30_clean.wav", "A.wav"]
    ]


def test_assign_cmp_answers_rejects_answer_outside_its_pair():
    """
    Reject explicit answer URLs that do not belong to their CMP pair.

    :return: None.
    """
    pairs = pd.DataFrame(
        {"pair_a": ["A.wav"], "pair_b": ["B.wav"], "pair_ans": ["C.wav"]}
    )
    displayed_pairs = np.array([["A.wav", "B.wav"] * 4])

    with pytest.raises(ValueError, match="pair_ans must match"):
        create_input._assign_cmp_answers(pairs, pd.DataFrame(index=[0]), displayed_pairs)


def test_balanced_ccr_padding_never_repeats_a_block():
    """
    Verify that the blocks padding the last balanced session come from other sessions.

    :return: None.
    """
    clips = [f"S{source:02d}_C{condition:02d}.wav" for source in range(5) for condition in range(4)]
    references = [f"reference-S{source:02d}.wav" for source in range(5) for _ in range(4)]
    for _ in range(30):
        output_df = pd.DataFrame()
        create_input.add_clips_balanced_block_ccr(pd.Series(clips), pd.Series(references),
                                                  r"(?P<source>S\d{2})_(?P<condition>C\d{2})\.wav",
                                                  "condition, source", 8, output_df)
        sessions = _session_items(output_df, 8, comparison=True)

        assert len(sessions) == 3
        for session in sessions:
            assert len(set(session)) == 8
            assert Counter(clip.split("_")[1] for clip, _ in session) == Counter(
                {f"C{condition:02d}.wav": 2 for condition in range(4)})


@pytest.mark.parametrize("block_keys", ["condition", "condition, source"])
@pytest.mark.parametrize("case", ["repeated", "padding", "shared_clip", "reversed"])
def test_balanced_ccr_packs_feasible_repeated_inputs(capsys, block_keys, case):
    """
    Retain repeated directed pairs, references and condition blocks without session duplicates.

    :param capsys: Captured generator messages.
    :param block_keys: One-key or two-key block design.
    :param case: Feasible input to pack.
    :return: None.
    """
    pairs = [(f"S{source:02d}_C{condition:02d}_{take}.wav", f"ref-{take}.wav")
             for source in range(2) for condition in range(2) for take in range(2)]
    if case == "repeated":
        pairs *= 3
    elif case == "padding":
        pairs += pairs[::2]
    elif case == "shared_clip":
        pairs = [(clip, reference) for clip, _ in pairs[::2] for reference in ("r1.wav", "r2.wav")]
    else:
        pairs[0] = (pairs[0][0], pairs[2][0])
        pairs[2] = (pairs[2][0], pairs[0][0])
    processed, references = zip(*pairs)
    for seed in range(3):
        create_input.random.seed(seed)
        output = pd.DataFrame()
        create_input.add_clips_balanced_block_ccr(pd.Series(processed), pd.Series(references),
                                                  r"(?P<source>S\d{2})_(?P<condition>C\d{2})_\d\.wav",
                                                  block_keys, 4, output)
        sessions = _session_items(output, 4, comparison=True)
        assert len(sessions) == -(-len(pairs) // 4)
        actual = Counter(pair for session in sessions for pair in session)
        assert not (Counter(pairs) - actual)
        assert set(actual) == set(pairs)
        for session in sessions:
            assert len({frozenset(pair) for pair in session}) == 4
            conditions = Counter(clip.split("_")[1] for clip, _ in session)
            assert conditions == {"C00": 2, "C01": 2}
            if "," in block_keys:
                cells = Counter(tuple(clip.split("_")[:2]) for clip, _ in session)
                for source in ("S00", "S01"):
                    assert cells[source, "C00"] == cells[source, "C01"]
        assert "WARNING:" not in capsys.readouterr().out


def test_balanced_ccr_padding_respects_repeated_pair_capacity():
    """
    Pad A,A,B independently in both conditions with B, retaining balanced sessions.

    :return: None.
    """
    clips = [f"{take}_C{condition}.wav" for condition in range(2) for take in ("A", "A", "B")]
    output = pd.DataFrame()
    create_input.add_clips_balanced_block_ccr(pd.Series(clips), pd.Series(["ref.wav"] * 6),
                                              r".*_C(?P<condition>\d)\.wav", "condition", 4, output)
    sessions = _session_items(output, 4, comparison=True)
    assert len(sessions) == 2
    assert all({clip for clip, _ in session} == set(clips) for session in sessions)


@pytest.mark.parametrize("comparison", [True, False], ids=["ccr", "acr"])
@pytest.mark.parametrize("case", ["too_few_blocks", "too_few_unique", "too_many_copies", "condition_capacity"])
def test_balanced_packing_warns_and_preserves_blocks_when_repeats_are_unavoidable(capsys, comparison, case):
    """
    Preserve coverage and balanced conditions with a warning when repeat-free packing is infeasible.

    :param capsys: Captured generator messages.
    :param comparison: Whether the CCR packer or the ACR packer is tested.
    :param case: Impossibility to exercise.
    :return: None.
    """
    if case == "too_few_blocks":
        clips = ["A_C0.wav", "A_C1.wav"]
    elif case == "too_few_unique":
        clips = ["A_C0.wav", "A_C1.wav"] * 2
    elif case == "too_many_copies":
        clips = ["A_C0.wav"] * 3 + ["B_C0.wav"] + ["A_C1.wav", "B_C1.wav"] * 2
    else:
        clips = ["A_C0.wav"] * 2 + ["B_C1.wav", "C_C1.wav"]
    output = pd.DataFrame()
    size = 8 if case == "too_few_blocks" else 4
    if comparison:
        listed = [(clip, "ref.wav") for clip in clips]
        create_input.add_clips_balanced_block_ccr(pd.Series(clips), pd.Series(["ref.wav"] * len(clips)),
                                                  r".*_C(?P<condition>\d)\.wav", "condition", size, output)
    else:
        listed = clips
        create_input.add_clips_balanced_block(pd.Series(clips), r".*_C(?P<condition>\d)\.wav",
                                              "condition", size, output)
    sessions = _session_items(output, size, comparison)
    assert len(sessions) == -(-len(listed) // size)
    assert any(len(set(session)) < size for session in sessions)
    actual = Counter(item for session in sessions for item in session)
    assert not (Counter(listed) - actual)
    assert set(actual) == set(listed)
    for session in sessions:
        conditions = Counter((item[0] if comparison else item).split("_")[1] for item in session)
        assert conditions == {"C0.wav": size // 2, "C1.wav": size // 2}
    warning = capsys.readouterr().out
    assert warning.count("WARNING: balanced_block") == 1
    assert "Continuing with repetitions within sessions." in warning


def test_acr_balanced_dispatch_packs_repeated_clips(tmp_path):
    """
    Pass clip values, not the dataframe's column name, through the ACR balanced path.

    :param tmp_path: Temporary output directory.
    :return: None.
    """
    clips = ["A_C0.wav", "B_C0.wav", "A_C1.wav", "B_C1.wav"] * 2
    data = pd.DataFrame({
        "rating_clips": clips, "math": ["math.wav"] * 8,
        "pair_a": ["40_a.wav"] * 8, "pair_b": ["50_b.wav"] * 8,
    })
    output_path = tmp_path / "balanced_acr.csv"
    create_input.create_input_for_mturk({
        "number_of_clips_per_session": "4", "number_of_trapping_per_session": "0",
        "number_of_gold_clips_per_session": "0", "clip_packing_strategy": "balanced_block",
        "condition_pattern": r".*_C(?P<condition>\d)\.wav", "block_keys": "condition",
    }, data, "acr", output_path)
    sessions = _session_items(pd.read_csv(output_path), 4, comparison=False)
    assert len(sessions) == 2
    assert all(set(session) == set(clips) for session in sessions)
