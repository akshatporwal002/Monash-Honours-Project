from app.services.rag.evaluation import EvaluationCaseResult, calculate_metrics


def test_retrieval_metrics_include_relevance_no_result_privacy_and_latency() -> None:
    metrics = calculate_metrics(
        [
            EvaluationCaseResult(frozenset({"a"}), ("a",), latency_ms=10),
            EvaluationCaseResult(frozenset({"b"}), ("x", "b"), latency_ms=30),
            EvaluationCaseResult(frozenset(), (), expected_no_result=True, latency_ms=20),
        ]
    )
    assert metrics["hit_at_1"] == 1 / 3
    assert metrics["hit_at_3"] == 2 / 3
    assert metrics["no_result_accuracy"] == 1.0
    assert metrics["cross_course_leakage_count"] == 0
    assert metrics["p50_latency_ms"] == 20
