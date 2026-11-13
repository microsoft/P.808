import configparser
import csv
import logging

import pandas as pd
import pytest

from src import result_parser
from src.result_parser import outliers_modified_z_score, outliers_z_score


@pytest.fixture
def ccr_config(monkeypatch):
    """
    Isolate CCR aggregation from CLI configuration and mutable parser globals.

    :param monkeypatch: Fixture for restoring module configuration after each test.
    :return: Minimal parser configuration, without an unused gold-question section.
    """
    cfg = configparser.ConfigParser()
    cfg.read_dict({"general": {}, "trapping": {"url_found_in": "input.tp"}, "accept_and_use": {}})
    monkeypatch.setattr(result_parser, "config", cfg, raising=False)
    monkeypatch.setattr(result_parser, "logger", logging.getLogger(__name__), raising=False)
    monkeypatch.setattr(result_parser, "question_names", ["q1"])
    monkeypatch.setattr(result_parser, "question_name_suffix", "")
    monkeypatch.setattr(result_parser, "max_found_per_file", -1)
    return cfg


def _ccr_session(score=0, order="rp", pair_id="pair-1", role="main"):
    """
    Create one canonical CCR response with a shared processed URL.

    :param score: Native P.808 canonical processed-minus-reference score.
    :param order: Presentation direction recorded by the native player.
    :param pair_id: Canonical comparison identity.
    :param role: Main, identical, or clean-B contrast.
    :return: Lowercase answer-export row.
    """
    return {
        "hitid": "hit", "workerid": "worker", "assignmentid": "assignment", "assignmentstatus": "Submitted",
        "input.bundle_id": "bundle-1",
        "answer.q1": str(score), "answer.q1_url": "https://example.test/shared-b.wav",
        "answer.q1_reference": f"https://example.test/{pair_id}-a.wav",
        "answer.q1_pair_id": pair_id, "answer.q1_role": role, "answer.q1_order": order,
    }


def test_ccr_zero_is_a_valid_judgment_without_gold_section(ccr_config):
    """
    Keep the CCR scale center instead of treating it as P.804 cannot-rate.

    :param ccr_config: Isolated legacy URL-based CCR configuration.
    :return: None.
    """
    files, _, workers = result_parser.transform("ccr", [_ccr_session()], False, False)
    assert files[0]["n"] == 1
    assert files[0]["CMOS"] == 0
    assert files[0]["cannot_rate_percentage"] == 0
    assert workers[0]["vote"] == 0


def test_ccr_pair_identity_separates_shared_audio_and_excludes_controls(ccr_config):
    """
    Aggregate canonical pairs rather than conflating comparisons sharing microphone B.

    :param ccr_config: Isolated configuration enabling explicit pair identity.
    :return: None.
    """
    ccr_config["general"]["aggregate_by_pair_id"] = "true"
    sessions = [
        _ccr_session(0), _ccr_session(2, "pr"), _ccr_session(-3, pair_id="pair-2"),
        _ccr_session(1, role="identical"), _ccr_session(2, role="contrast"),
    ]
    files, _, workers = result_parser.transform("ccr", sessions, False, False)
    by_id = {row["file_url"]: row for row in files}
    assert by_id["pair-1"]["n"] == 2
    assert by_id["pair-1"]["CMOS"] == 1
    assert by_id["pair-2"]["CMOS"] == -3
    assert len(workers) == 3
    assert workers[1]["canonical_b_minus_a"] == 2
    assert workers[1]["presentation_score"] == -2
    assert workers[1]["reference_url"].endswith("pair-1-a.wav")


@pytest.mark.parametrize("order,raw", [("rp", 2), ("pr", -2)])
def test_ccr_contrast_uses_clean_preference_in_both_directions(order, raw):
    """
    Interpret the already-normalized native CCR value exactly once.

    :param order: Realized order.
    :param raw: Expected second-minus-first judgment.
    :return: None.
    """
    trial = result_parser.ccr_trial(_ccr_session(2, order, role="contrast"), "q1")
    assert trial["presentation_score"] == raw
    assert trial["canonical_b_minus_a"] == 2
    assert trial["bundle_id"] == "bundle-1"
    assert trial["passes_contrast"]


@pytest.mark.parametrize("field,value", [
    ("answer.q1", "2.5"), ("answer.q1", "4"),
    ("answer.q1_order", "ab"), ("answer.q1_pair_id", ""), ("answer.q1_role", ""),
])
def test_ccr_metadata_errors_are_not_silently_aggregated(field, value):
    """
    Fail loudly when identity, direction or score cannot be interpreted reliably.

    :param field: Export field to invalidate.
    :param value: Invalid field content.
    :return: None.
    """
    session = _ccr_session()
    session[field] = value
    with pytest.raises(ValueError):
        result_parser.ccr_trial(session, "q1")


def test_ccr_audit_preserves_zero_and_both_unselected_control_policies(tmp_path, ccr_config, monkeypatch):
    """
    Export raw observations before filtering without choosing acceptance or payment.

    :param tmp_path: Temporary answer/export directory.
    :param ccr_config: Isolated parser configuration.
    :param monkeypatch: Fixture for specifying realized question names.
    :return: None.
    """
    monkeypatch.setattr(result_parser, "question_names", ["q1", "q2", "q3"])
    session = _ccr_session()
    for number, role, score in [(2, "identical", 1), (3, "contrast", 2)]:
        for key, value in _ccr_session(score, role=role, pair_id=role).items():
            if key.startswith("answer.q1"):
                session[key.replace("answer.q1", f"answer.q{number}")] = value
    path = tmp_path / "answers.csv"
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=[key.title() for key in session])
        writer.writeheader()
        writer.writerow({key.title(): value for key, value in session.items()})
    result_parser.export_ccr_audit(str(path))
    trials = pd.read_csv(tmp_path / "answers_ccr_raw_trials.csv")
    policies = pd.read_csv(tmp_path / "answers_ccr_control_candidates.csv", keep_default_na=False)
    assert trials["canonical_b_minus_a"].tolist() == [0, 1, 2]
    assert trials["bundle_id"].tolist() == ["bundle-1"] * 3
    assert not policies.iloc[0]["identical_exact_zero"]
    assert policies.iloc[0]["identical_within_one"]
    assert policies.iloc[0]["bundle_id"] == "bundle-1"
    assert policies.iloc[0]["acceptance_decision"] == policies.iloc[0]["payment_decision"] == ""


def test_ccr_pair_identity_skips_unannotated_trap_before_decoding(tmp_path, ccr_config, monkeypatch):
    """
    Keep the default legacy trap outside metadata-enabled pair aggregation.

    :param tmp_path: Temporary answer/export directory.
    :param ccr_config: Isolated parser configuration.
    :param monkeypatch: Fixture for specifying realized question names.
    :return: None.
    """
    ccr_config["general"]["aggregate_by_pair_id"] = "true"
    monkeypatch.setattr(result_parser, "question_names", ["q1", "q2"])
    session = _ccr_session()
    trap_url = "https://example.test/trap.wav"
    session.update({"input.tp": trap_url, "answer.q1": "-1", "answer.q1_url": trap_url})
    for suffix in ("_reference", "_pair_id", "_role", "_order", "_practice_exposure"):
        session.pop(f"answer.q1{suffix}", None)
    for key, value in _ccr_session(score=2).items():
        if key.startswith("answer.q1"):
            session[key.replace("answer.q1", "answer.q2")] = value

    path = tmp_path / "answers.csv"
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=[key.title() for key in session])
        writer.writeheader()
        writer.writerow({key.title(): value for key, value in session.items()})

    result_parser.export_ccr_audit(str(path))
    trials = pd.read_csv(tmp_path / "answers_ccr_raw_trials.csv")
    assert trials["question"].tolist() == ["q2"]

    files, _, workers = result_parser.transform("ccr", [session], False, False)
    assert [row["file_url"] for row in files] == ["pair-1"]
    assert [row["question"] for row in workers] == ["q2"]


def test_p804_cannot_rate_still_excludes_zero(ccr_config, monkeypatch):
    """
    Preserve the existing cannot-rate behavior on eligible P.804 dimensions.

    :param ccr_config: Isolated common aggregation configuration.
    :param monkeypatch: Fixture for selecting the P.804 signal-quality dimension.
    :return: None.
    """
    ccr_config["gold_question"] = {"url_found_in": "input.gold"}
    monkeypatch.setattr(result_parser, "question_name_suffix", "_sig")
    session = _ccr_session()
    session.update({"input.gold": "not-this-url", "answer.q1_sig": "0"})
    files, _, _ = result_parser.transform("p804", [session], False, False)
    assert files[0]["n"] == 0
    assert files[0]["cannot_rate_percentage"] == 100


def test_outliers_modified_z_score_removes_clear_outlier():
    """
    Verify that the modified z-score filter removes a clear outlier.

    :return: None.
    """
    votes = [1, 2, 2, 2, 3, 100]

    assert outliers_modified_z_score(votes) == [1, 2, 2, 2, 3]


def test_outliers_z_score_preserves_constant_votes():
    """
    Verify that the z-score filter preserves votes with no variance.

    :return: None.
    """
    votes = [3, 3, 3]

    assert outliers_z_score(votes) == votes


def test_outliers_z_score_uses_threshold():
    """
    Verify that the z-score cutoff distinguishes values around the threshold.

    :return: None.
    """
    below_threshold = [10] * 10 + [1000]
    above_threshold = [10] * 11 + [1000]

    assert outliers_z_score(below_threshold) == below_threshold
    assert outliers_z_score(above_threshold) == [10] * 11
