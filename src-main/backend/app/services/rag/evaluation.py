"""Deterministic retrieval evaluation metrics for educator-approved datasets."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    relevant_chunk_ids: frozenset[str]
    retrieved_chunk_ids: tuple[str, ...]
    expected_no_result: bool = False
    latency_ms: int = 0
    leaked_cross_course: bool = False


def calculate_metrics(cases: list[EvaluationCaseResult]) -> dict[str, float | int]:
    if not cases:
        raise ValueError("at least one evaluation case is required")

    def hit_at(limit: int) -> float:
        return sum(
            bool(set(item.retrieved_chunk_ids[:limit]) & item.relevant_chunk_ids) for item in cases
        ) / len(cases)

    reciprocal_ranks = []
    no_result_correct = []
    for item in cases:
        rank = next(
            (
                index + 1
                for index, chunk_id in enumerate(item.retrieved_chunk_ids)
                if chunk_id in item.relevant_chunk_ids
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        if item.expected_no_result:
            no_result_correct.append(not item.retrieved_chunk_ids)
    latencies = sorted(item.latency_ms for item in cases)
    return {
        "hit_at_1": hit_at(1),
        "hit_at_3": hit_at(3),
        "hit_at_5": hit_at(5),
        "mean_reciprocal_rank": sum(reciprocal_ranks) / len(cases),
        "no_result_accuracy": sum(no_result_correct) / len(no_result_correct)
        if no_result_correct
        else 1.0,
        "cross_course_leakage_count": sum(item.leaked_cross_course for item in cases),
        "p50_latency_ms": median(latencies),
        "p95_latency_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)],
    }
