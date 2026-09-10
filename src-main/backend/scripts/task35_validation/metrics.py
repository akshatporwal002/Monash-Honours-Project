"""Separate denominators and uncertainty; no composite approval score."""

import math
import random
from collections import defaultdict


def rate(events: list[bool]) -> dict:
    n, k = len(events), sum(events)
    if not n:
        return {"numerator": 0, "denominator": 0, "estimate": None, "wilson_95": None}
    z = 1.959963984540054
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "numerator": k,
        "denominator": n,
        "estimate": p,
        "wilson_95": [max(0.0, center - half), min(1.0, center + half)],
    }


def mean_rating(values: list[float]) -> dict:
    n = len(values)
    # Distribution-free Hoeffding bound for independent bounded [1,5] ratings.
    estimate = sum(values) / n if n else None
    half = 4 * math.sqrt(math.log(40) / (2 * n)) if n else None
    return {
        "sum": sum(values),
        "denominator": n,
        "estimate": estimate,
        "hoeffding_95": [max(1.0, estimate - half), min(5.0, estimate + half)] if n else None,
    }


def agreement(pairs: list[tuple[str, str]]) -> dict:
    result = rate([a == b for a, b in pairs])
    n = len(pairs)
    labels = sorted({v for pair in pairs for v in pair})
    expected = (
        sum(sum(a == v for a, _ in pairs) * sum(b == v for _, b in pairs) for v in labels) / n**2
        if n
        else None
    )
    result["cohen_kappa"] = (
        (result["estimate"] - expected) / (1 - expected) if n and expected < 1 else None
    )
    result["kappa_undefined_reason"] = (
        "zero_denominator" if not n else "constant_marginals" if expected == 1 else None
    )
    result["confusion"] = {
        a: {b: sum(x == a and y == b for x, y in pairs) for b in labels} for a in labels
    }
    return result


def clustered_interval(samples: list[tuple[str, float]]) -> dict:
    """Exploratory percentile bootstrap of entire scenario families, fixed seed."""
    clusters = defaultdict(list)
    for family, value in samples:
        clusters[family].append(value)
    keys = sorted(clusters)
    if len(keys) < 2:
        return {"families": len(keys), "cluster_percentile_95": None}
    rng = random.Random(35)
    estimates = []
    for _ in range(1000):
        values = [v for k in rng.choices(keys, k=len(keys)) for v in clusters[k]]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    return {"families": len(keys), "cluster_percentile_95": [estimates[24], estimates[974]]}
