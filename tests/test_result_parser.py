from src.result_parser import outliers_modified_z_score, outliers_z_score


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


def test_outliers_z_score_uses_configured_threshold():
    """
    Verify that values below the configured z-score threshold remain.

    :return: None.
    """
    votes = [10, 10, 10, 1000]

    assert outliers_z_score(votes) == votes
