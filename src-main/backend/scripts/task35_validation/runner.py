"""Read recorded outputs and independent ratings without providers or learner storage."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import ValidationError

from scripts.task35_validation.metrics import agreement, clustered_interval, mean_rating, rate
from scripts.task35_validation.schema import DIMENSIONS, Bundle, Manifest

REQUIRED_FILES = (
    "docs/01-implementation-requirements.md",
    "docs/02-pass-incomplete-bloom-assessment-spec.md",
    "docs/learnlens/task-08-approved-selections.md",
    "src-main/backend/app/services/quantum.py",
    "src-main/backend/app/services/quantum_runner.py",
    "src-main/backend/app/services/feedback/prompt.py",
    "src-main/backend/app/services/feedback/judge.py",
    "src-main/backend/app/services/feedback/quality_review.py",
    "src-main/backend/app/services/feedback/assessed.py",
    "src-main/backend/app/services/feedback/contracts.py",
    "src-main/backend/app/services/feedback/agent.py",
    "src-main/backend/app/services/feedback/pipeline.py",
    "src-main/backend/app/services/feedback/context.py",
    "src-main/backend/app/services/feedback/runtime.py",
    "src-main/backend/app/services/feedback/application.py",
    "src-main/backend/app/services/feedback/repository.py",
    "src-main/backend/app/services/feedback/worker.py",
    "src-main/backend/app/api/background_execution.py",
    "src-main/backend/app/api/feedback_dependencies.py",
    "src-main/backend/app/api/assessment_dependencies.py",
    "src-main/backend/app/api/routes/lms.py",
    "src-main/backend/app/api/routes/feedback.py",
    "src-main/backend/app/api/routes/activity_continuation.py",
    "src-main/backend/app/services/runtime_policy.py",
    "src-main/backend/app/services/llm.py",
    "src-main/backend/app/services/task_generation_runtime.py",
    "src-main/backend/app/services/feedback/practice_evidence.py",
    "src-main/backend/app/schemas/feedback.py",
    "src-main/backend/app/schemas/assessed_feedback.py",
    "src-main/backend/app/schemas/persistence.py",
    "src-main/backend/app/models/persistence.py",
    "src-main/backend/app/models/feedback_review_history.py",
    "src-main/backend/app/schemas/episode.py",
    "src-main/backend/app/services/episode_evidence.py",
    "src-main/backend/app/services/episode_responses.py",
    "src-main/backend/app/services/assessment/feedback_context.py",
    "src-main/backend/app/services/assessment/evaluators.py",
    "src-main/backend/app/services/assessment/evaluation.py",
    "src-main/backend/app/services/assessment/pass_rules.py",
    "src-main/backend/app/services/assessment/rule_settings.py",
    "src-main/backend/app/services/assessment/moderation.py",
    "src-main/backend/app/services/assessment/evaluator_release.py",
    "src-main/backend/app/models/assessment_moderation.py",
    "src-main/backend/app/api/routes/assessment_moderation.py",
    "src-main/backend/app/schemas/assessment_moderation.py",
    "src-main/backend/app/services/provider_usage.py",
    "src-main/backend/app/services/material_scanning.py",
    "src-main/backend/app/services/task_review.py",
    "src-main/backend/app/services/task_types.py",
    "src-main/backend/app/services/structured_generation.py",
    "src-main/backend/app/services/local_ai.py",
    "src-main/backend/app/services/rag/task_generation.py",
    "src-main/backend/app/schemas/choice_tasks.py",
    "src-main/backend/app/schemas/structured_tasks.py",
    "src-main/backend/app/schemas/generated_task_design.py",
    "src-main/backend/app/schemas/support_representations.py",
    "src-main/backend/app/services/episode_support.py",
    "src-main/backend/app/services/evidence/live.py",
    "src-main/backend/app/services/assessment/generated_design.py",
    "src-main/backend/app/services/assessment/publication.py",
    "src-main/backend/app/services/assessment/definitions.py",
    "src-main/backend/app/services/assessment/submissions.py",
    "src-main/backend/app/services/validation_reads.py",
    "src-main/backend/app/services/assessment/transfer_boundary.py",
    "src-main/backend/app/services/multipart_generation.py",
    "src-main/backend/app/schemas/multipart_generation.py",
    "src-main/backend/app/services/practice_representations.py",
    "src-main/backend/app/schemas/practice_representations.py",
    "src-main/backend/app/services/integrity_cues.py",
    "src-main/backend/app/services/tutor.py",
    "src-main/backend/app/services/lms.py",
    "src-main/backend/app/schemas/lms.py",
    "src-main/backend/app/api/routes/assessment.py",
    # Retrieval and the exact source/task context supplied to generation and feedback.
    "src-main/backend/app/core/config.py",
    "src-main/backend/app/services/rag/runtime.py",
    "src-main/backend/app/services/rag/vector_retrieval.py",
    "src-main/backend/app/services/rag/local_vectors.py",
    "src-main/backend/app/services/rag/local_retrieval.py",
    "src-main/backend/app/services/rag/retrieval.py",
    "src-main/backend/app/services/rag/normalisation.py",
    "src-main/backend/app/services/rag/source_history.py",
    "src-main/backend/app/services/rag/contracts.py",
    "src-main/backend/app/services/rag/feedback_adapter.py",
    "src-main/backend/app/services/task_context.py",
    "src-main/backend/app/services/generation_context.py",
    "src-main/backend/app/schemas/generation_context.py",
    "src-main/backend/app/services/source_episode_generation.py",
    "src-main/backend/app/api/routes/task_generation.py",
    # Category review, alignment and representation gates change delivered content.
    "src-main/backend/app/domain/assessment.py",
    "src-main/backend/app/services/category_review.py",
    "src-main/backend/app/services/task_category_review.py",
    "src-main/backend/app/services/category_selection_review.py",
    "src-main/backend/app/models/task_review.py",
    "src-main/backend/app/schemas/category_review.py",
    "src-main/backend/app/schemas/task_review.py",
    "src-main/backend/app/api/routes/task_review.py",
    "src-main/backend/app/services/assessment/alignment.py",
    "src-main/backend/app/services/assessment/alignment_contract.py",
    "src-main/backend/app/services/episode_contract.py",
    "src-main/backend/app/services/episodes.py",
    "src-main/backend/app/services/representation_generation.py",
    "src-main/backend/app/services/representation_drafts.py",
    "src-main/backend/app/schemas/representation_generation.py",
    "src-main/backend/app/api/routes/practice_representations.py",
    # Reviewed profile evidence feeds uncertain progress and approved next-step selection.
    "src-main/backend/app/domain/platform_enums.py",
    "src-main/backend/app/services/learner_model/builder.py",
    "src-main/backend/app/services/learner_model/contracts.py",
    "src-main/backend/app/services/learner_model/safety.py",
    "src-main/backend/app/services/learner_model/profile_reviews.py",
    "src-main/backend/app/services/learner_model/repository.py",
    "src-main/backend/app/services/learning_progress.py",
    "src-main/backend/app/services/progress_indicators.py",
    "src-main/backend/app/schemas/progress.py",
    "src-main/backend/app/services/continuation/activity.py",
    "src-main/backend/app/services/continuation/repository.py",
    "src-main/backend/app/services/terminal_integrations/repository.py",
    "src-main/backend/app/services/terminal_integrations/worker.py",
    "src-main/backend/app/services/curriculum.py",
    # Importing governed suggestions must invalidate earlier assessment evidence too.
    "src-main/backend/app/services/assessment/suggestions.py",
    "src-main/backend/app/schemas/evaluator_governance.py",
    "src-main/backend/tests/fixtures/task35_validation/scenarios.json",
    "src-main/backend/scripts/task35_validation/__init__.py",
    "src-main/backend/scripts/task35_validation/schema.py",
    "src-main/backend/scripts/task35_validation/metrics.py",
    "src-main/backend/scripts/task35_validation/runner.py",
    "src-main/backend/scripts/task35_validation/prepare.py",
)
CHANNELS = ("task", "feedback", "evaluation", "judge", "assessment")


def digest(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


def file_digest(path: Path) -> str:
    # Canonical newlines make Git CRLF checkouts equivalent; other edits invalidate evidence.
    return hashlib.sha256(
        path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8")
    ).hexdigest()


def thresholds(root: Path) -> dict:
    text = (root / REQUIRED_FILES[0]).read_text(encoding="utf-8")
    import re

    patterns = {
        "minimum_cases": r"Across at least (\d+) educator-approved quantum cases",
        "factual_accuracy": r"at least (\d+) percent of generated tasks, feedback, and evaluations",
        "hallucination": r"Hallucination rate must be no more than (\d+) percent",
        "feedback_rating": r"Educator review average must be at least (\d+) out of 5",
        "next_action": r"At least (\d+) percent of sampled incomplete responses",
        "flawed_rejection": r"judge must reject at least (\d+) percent",
        "false_rejection": r"falsely reject no more than (\d+) percent",
    }
    values = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(
                f"controlling threshold not found: {name}; human reconciliation required"
            )
        values[name] = int(match[1]) / (1 if name in {"minimum_cases", "feedback_rating"} else 100)
    return values


def manifest_issues(recorded: Manifest, current: Manifest, root: Path) -> list[str]:
    issues = []
    if digest(recorded) != digest(current):
        issues.append("recorded/current manifest mismatch")
    if not set(REQUIRED_FILES).issubset(current.files):
        issues.append("required artifact fingerprints missing")
    for relative, expected in current.files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            issues.append(f"manifest path outside repository: {relative}")
        elif not path.is_file() or file_digest(path) != expected:
            issues.append(f"stale artifact: {relative}")
    return issues


def unique(items, key, label):
    result = {}
    for item in items:
        identity = key(item)
        if identity in result:
            raise ValueError(f"duplicate {label}: {identity}")
        result[identity] = item
    return result


def validate_links(bundle: Bundle):
    cases = unique(bundle.cases, lambda x: x.case_id, "case")
    reviewers = unique(bundle.reviewers, lambda x: x.reviewer_id, "reviewer")
    if len({r.name.casefold().strip() for r in bundle.reviewers}) != len(reviewers):
        raise ValueError("one named reviewer cannot occupy multiple independent slots")
    outputs = unique(bundle.outputs, lambda x: (x.case_id, x.channel), "output")
    ratings = unique(bundle.ratings, lambda x: x.rating_id, "rating id")
    unique(bundle.ratings, lambda x: (x.case_id, x.channel, x.reviewer_id), "independent rating")
    adjudications = unique(bundle.adjudications, lambda x: (x.case_id, x.channel), "adjudication")
    unique(bundle.approvals, lambda x: x.case_id, "case approval")
    manifest_digest = digest(bundle.manifest)
    source_ids = {s.get("id") for s in bundle.manifest.source_references}
    for case in cases.values():
        if not set(case.source_ids).issubset(source_ids):
            raise ValueError("case references unknown source")
    for item in [*bundle.outputs, *bundle.ratings, *bundle.approvals]:
        if item.case_id not in cases:
            raise ValueError("unknown case reference")
        if item.case_digest != digest(cases[item.case_id]):
            raise ValueError("stale case reference")
        if item.manifest_digest != manifest_digest:
            raise ValueError("stale manifest reference")
        if hasattr(item, "reviewer_id") and item.reviewer_id not in reviewers:
            raise ValueError("unknown reviewer reference")
    for rating in bundle.ratings:
        if rating.channel != "assessment":
            output = outputs.get((rating.case_id, rating.channel))
            if output is None or rating.output_digest != digest(output):
                raise ValueError("stale or missing rated output")
    for adj in adjudications.values():
        if adj.case_id not in cases or adj.reviewer_id not in reviewers:
            raise ValueError("unknown adjudication reference")
        originals = [ratings.get(rid) for rid in adj.rating_ids]
        if len(set(adj.rating_ids)) != 2 or any(r is None for r in originals):
            raise ValueError("adjudication must reference two original ratings")
        if any(
            (r.case_id, r.channel) != (adj.case_id, adj.channel) or r.state != "RATED"
            for r in originals
        ):
            raise ValueError("adjudication reference scope/state mismatch")
        if adj.reviewer_id in {r.reviewer_id for r in originals}:
            raise ValueError("adjudicator must be an independent third reviewer")
    for item in [*bundle.outputs, *bundle.ratings, *bundle.adjudications]:
        if item.channel != "assessment":
            continue
        values = item if hasattr(item, "result") else item.values
        if values is not None and values.criteria is not None:
            if set(values.criteria) != set(cases[item.case_id].criteria):
                raise ValueError("assessment criterion scope mismatch")
    return cases, outputs, adjudications


def calculate(rows: list[dict]) -> dict:
    result = {}

    def binary(name, selected, event):
        events = [event(r) for r in selected]
        result[name] = rate(events) | clustered_interval(
            [(r["case"].family, float(v)) for r, v in zip(selected, events, strict=True)]
        )

    for channel in ("task", "feedback", "evaluation"):
        selected = [r for r in rows if r["channel"] == channel]
        binary(f"{channel}.factual_accuracy", selected, lambda r: r["gold"].factual_correct)
        binary(f"{channel}.hallucination", selected, lambda r: r["gold"].hallucination)
    feedback = [r for r in rows if r["channel"] == "feedback"]
    for dimension in DIMENSIONS:
        scores = [
            sum(v.feedback_ratings[dimension] for v in r["independent_values"]) / 2
            for r in feedback
        ]
        result[f"feedback.{dimension}"] = mean_rating(scores) | clustered_interval(
            [(r["case"].family, v) for r, v in zip(feedback, scores, strict=True)]
        )
    binary(
        "feedback.next_action",
        [r for r in feedback if r["gold"].incomplete_response],
        lambda r: r["gold"].next_action_and_revision,
    )
    judge = [r for r in rows if r["channel"] == "judge"]
    binary(
        "judge.flawed_rejection",
        [r for r in judge if r["gold"].flawed],
        lambda r: r["output"].judge_decision == "REJECTED",
    )
    binary(
        "judge.false_rejection",
        [r for r in judge if not r["gold"].flawed],
        lambda r: r["output"].judge_decision == "REJECTED",
    )
    assessments = [r for r in rows if r["channel"] == "assessment"]
    binary(
        "assessment.false_pass",
        [r for r in assessments if r["gold"].result == "INCOMPLETE"],
        lambda r: r["output"].result == "PASS",
    )
    binary(
        "assessment.false_incomplete",
        [r for r in assessments if r["gold"].result == "PASS"],
        lambda r: r["output"].result == "INCOMPLETE",
    )
    result["assessment.result_agreement"] = agreement(
        [(r["gold"].result, r["output"].result) for r in assessments]
    ) | clustered_interval(
        [(r["case"].family, float(r["gold"].result == r["output"].result)) for r in assessments]
    )
    for criterion in sorted({k for r in assessments for k in r["case"].criteria}):
        selected = [r for r in assessments if criterion in r["case"].criteria]
        result[f"assessment.{criterion}.agreement"] = agreement(
            [(r["gold"].criteria[criterion], r["output"].criteria[criterion]) for r in selected]
        ) | clustered_interval(
            [
                (
                    r["case"].family,
                    float(r["gold"].criteria[criterion] == r["output"].criteria[criterion]),
                )
                for r in selected
            ]
        )
    return result


def run(bundle: Bundle, current: Manifest, root: Path) -> dict:
    cases, outputs, adjudications = validate_links(bundle)
    issues = manifest_issues(bundle.manifest, current, root)
    limits = thresholds(root)
    approved = {x.case_id for x in bundle.approvals}
    review_groups = defaultdict(list)
    for rating in bundle.ratings:
        review_groups[rating.case_id, rating.channel].append(rating)
    rows, baseline = [], defaultdict(list)
    exclusions = Counter()
    for case in cases.values():
        for channel in CHANNELS:
            key = (case.case_id, channel)
            output = outputs.get(key)
            reviews = review_groups[key]
            valid = sorted((r for r in reviews if r.state == "RATED"), key=lambda r: r.reviewer_id)
            if len(reviews) == 2 and len(valid) == 2 and channel == "assessment":
                pair = (valid[0].reviewer_id, valid[1].reviewer_id)
                for criterion in case.criteria:
                    baseline[case.task_type, criterion, pair].append(
                        (
                            case.family,
                            valid[0].values.criteria[criterion],
                            valid[1].values.criteria[criterion],
                        )
                    )
                baseline[case.task_type, "result", pair].append(
                    (case.family, valid[0].values.result, valid[1].values.result)
                )
            # Exclusive omission reason, in this documented priority order.
            reason = None
            if output is None:
                reason = "missing_output"
            elif output.state != "RECORDED":
                reason = f"output_{output.state.lower()}"
            elif len(reviews) != 2:
                reason = "requires_exactly_two_independent_ratings"
            elif len(valid) != 2:
                reason = "rating_abstained_or_invalid"
            if reason:
                exclusions[f"{channel}.{reason}"] += 1
                continue
            gold = valid[0].values
            if gold != valid[1].values:
                adj = adjudications.get(key)
                if adj is None or set(adj.rating_ids) != {r.rating_id for r in valid}:
                    exclusions[f"{channel}.unresolved_disagreement"] += 1
                    continue
                gold = adj.values
            elif key in adjudications:
                gold = adjudications[key].values
            rows.append(
                {
                    "case": case,
                    "channel": channel,
                    "gold": gold,
                    "output": output,
                    "independent_values": [r.values for r in valid],
                }
            )
    metrics = calculate(rows)
    comparisons = {}
    for name, metric in metrics.items():
        target = None
        maximum = False
        if name.endswith(".factual_accuracy"):
            target = limits["factual_accuracy"]
        elif name.endswith(".hallucination"):
            target, maximum = limits["hallucination"], True
        elif name in {f"feedback.{d}" for d in DIMENSIONS}:
            target = limits["feedback_rating"]
        elif name == "feedback.next_action":
            target = limits["next_action"]
        elif name == "judge.flawed_rejection":
            target = limits["flawed_rejection"]
        elif name == "judge.false_rejection":
            target, maximum = limits["false_rejection"], True
        if target is not None:
            value = metric["estimate"]
            comparisons[name] = {
                "threshold": target,
                "direction": "at_most" if maximum else "at_least",
                "observed_target": "UNVERIFIED"
                if value is None
                else "MET"
                if (value <= target if maximum else value >= target)
                else "NOT_MET",
            }
    blockers = list(issues)
    if bundle.provenance != "EXPERT_RECORDED" or bundle.manifest.provenance != "RECORDED":
        blockers.append("draft/synthetic evidence is not expert validation")
    if any("NOT_RUN" in v or "DRAFT" in v for v in bundle.manifest.components.values()):
        blockers.append("actual model and validation versions remain unrecorded")
    for source in bundle.manifest.source_references:
        if (
            not source.get("approval_reference")
            or source.get("immutable_artifact") not in bundle.manifest.files
        ):
            blockers.append(f"approved immutable source evidence missing: {source.get('id')}")
    if len(approved) < limits["minimum_cases"] or len(approved) != len(cases):
        blockers.append("every case requires educator approval; at least 100 are required")
    if any(not k.startswith("assessment.") for k in exclusions):
        blockers.append("incomplete required content/feedback/judge outputs or ratings")
    if any(v["observed_target"] == "UNVERIFIED" for v in comparisons.values()):
        blockers.append("required measure has zero denominator")
    status = (
        "UNVERIFIED"
        if blockers
        else (
            "TARGETS_MET"
            if all(v["observed_target"] == "MET" for v in comparisons.values())
            else "TARGETS_NOT_MET"
        )
    )
    strata = {}
    for dimension in ("task_type", "variant", "access_form", "style", "stage"):
        strata[dimension] = {
            value: calculate([r for r in rows if getattr(r["case"], dimension) == value])
            for value in sorted({getattr(c, dimension) for c in cases.values()})
        }
    return {
        "report_version": "task35-report-v1",
        "provenance": bundle.provenance,
        "manifest_digest": digest(bundle.manifest),
        "case_count": len(cases),
        "approved_cases": len(approved),
        "eligible_case_channel_pairs": len(cases) * len(CHANNELS),
        "included_pairs": len(rows),
        "exclusions": dict(sorted(exclusions.items())),
        "rating_states": dict(Counter(r.state for r in bundle.ratings)),
        "thresholds": limits,
        "metrics": metrics,
        "strata": strata,
        "human_baseline": {
            f"{task}.{criterion}.{pair[0]}:{pair[1]}": agreement([(a, b) for _, a, b in samples])
            | clustered_interval([(family, float(a == b)) for family, a, b in samples])
            for (task, criterion, pair), samples in sorted(baseline.items())
        },
        "target_comparisons": comparisons,
        "content_feedback_judge_status": status,
        "blockers": blockers,
        "ai_assessment_release": "PENDING",
        "operational_ai_suggestions_enabled": False,
        "assessment_release_missing": [
            "approved numerical error limits and statistic",
            "named expert sign-off and trained-human baseline",
            "fairness/access review",
            "task-specific review triggers and revalidation rules",
            "recorded release decision",
        ],
        "uncertainty": "Wilson/Hoeffding intervals assume independent units. Matched variants are "
        "clustered by scenario family: use exploratory family-bootstrap intervals where supplied. "
        "Convenience drafts do not estimate population performance; small strata are inconclusive. "
        "Kappa is descriptive, with null for constant marginals; no kappa release limit is assumed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--current-manifest", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = Bundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
        current = Manifest.model_validate_json(args.current_manifest.read_text(encoding="utf-8"))
        report = run(bundle, current, args.repo)
        exit_code = 0
    except (ValidationError, ValueError, OSError) as error:
        report = {
            "content_feedback_judge_status": "UNVERIFIED",
            "ai_assessment_release": "PENDING",
            "operational_ai_suggestions_enabled": False,
            "import_error": str(error),
        }
        exit_code = 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: report[k] for k in ("content_feedback_judge_status", "ai_assessment_release")}
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
