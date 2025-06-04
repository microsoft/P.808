from src.result_parser import outliers_modified_z_score, outliers_z_score


def test_outliers_modified_z_score_removes_outlier():
    data = [1, 1, 1, 100]
    assert outliers_modified_z_score(data) == [1, 1, 1]


def test_outliers_z_score_threshold_high():
    data = [10, 10, 10, 1000]
    # With default threshold 3.29 the outlier is not removed
    assert outliers_z_score(data) == data
