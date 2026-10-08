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


def test_outliers_z_score_uses_threshold():
    """
    Verify that the z-score cutoff distinguishes values around the threshold.

    :return: None.
    """
    below_threshold = [10] * 10 + [1000]
    above_threshold = [10] * 11 + [1000]

    assert outliers_z_score(below_threshold) == below_threshold
    assert outliers_z_score(above_threshold) == [10] * 11
