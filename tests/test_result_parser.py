import configparser
import logging

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
