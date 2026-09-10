"""Hand-counted synthetic examples, not expert validation evidence."""

import pytest

from scripts.task35_validation.metrics import agreement, clustered_interval, mean_rating, rate


def test_binary_denominators_and_wilson_bounds():
    result = rate([True, False, True, True])
    assert (result["numerator"], result["denominator"], result["estimate"]) == (3, 4, 0.75)
    assert result["wilson_95"] == pytest.approx([0.300641842582402, 0.954412739190299])
    assert rate([True] * 4)["wilson_95"][0] < 1
    assert rate([False] * 4)["wilson_95"][1] > 0


def test_zero_denominators_are_not_perfect_results():
    assert rate([])["estimate"] is None
    assert mean_rating([])["estimate"] is None
    assert agreement([])["cohen_kappa"] is None
    assert agreement([])["kappa_undefined_reason"] == "zero_denominator"


def test_kappa_and_constant_marginals():
    result = agreement(
        [("MET", "MET"), ("MET", "NOT_MET"), ("NOT_MET", "NOT_MET"), ("NOT_MET", "MET")]
    )
    assert result["estimate"] == 0.5
    assert result["cohen_kappa"] == 0
    assert result["confusion"]["MET"]["NOT_MET"] == 1
    assert agreement([("MET", "MET")])["cohen_kappa"] is None
    assert agreement([("MET", "MET")])["kappa_undefined_reason"] == "constant_marginals"


def test_rating_interval_and_clustered_variants():
    assert mean_rating([1, 3, 5])["estimate"] == 3
    assert mean_rating([1, 3, 5])["hoeffding_95"] == [1, 5]
    assert clustered_interval([("a", 1), ("a", 0)])["cluster_percentile_95"] is None
    data = [("a", 1)] * 9 + [("b", 0)] * 9
    assert clustered_interval(data) == clustered_interval(data)
    assert clustered_interval(data)["cluster_percentile_95"] == [0, 1]
