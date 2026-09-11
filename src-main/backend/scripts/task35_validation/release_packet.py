"""Prepare an administrator import packet from actual reviews and signed approval records.

This command records no approval and never releases or invokes an evaluator.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import AwareDatetime, Field, TypeAdapter

from app.schemas.evaluator_governance import (
    AssessmentGateEvidence,
    Fingerprint,
    GovernanceWrite,
    Reference,
)
from scripts.task35_validation.runner import digest, run
from scripts.task35_validation.schema import Bundle, Manifest


class ApprovalRecord(GovernanceWrite):
    release_approval: Reference
    expert_review: Reference
    approved_cases: Reference
    human_agreement: Reference
    fairness_review: Reference
    revalidation_policy: Reference
    threshold_approval: Reference
    max_false_pass: float = Field(ge=0, le=1, allow_inf_nan=False)
    max_false_incomplete: float = Field(ge=0, le=1, allow_inf_nan=False)
    assessment_gate: AssessmentGateEvidence
    baseline_key: Reference


def prepare_packet(bundle, current, root, approval, fingerprint, expires_at):
    fingerprint = TypeAdapter(Fingerprint).validate_python(fingerprint)
    expires_at = TypeAdapter(AwareDatetime).validate_python(expires_at)
    if expires_at <= datetime.now(UTC):
        raise ValueError("Validation expiry must be in the future")
    approval = ApprovalRecord.model_validate(approval)
    report = run(bundle, current, root)
    if report["content_feedback_judge_status"] != "TARGETS_MET":
        raise ValueError("Current recorded validation has not met its required targets")
    if report["exclusions"]:
        raise ValueError("Complete and adjudicate every assessment case before release preparation")
    gate = approval.assessment_gate
    if gate.case_count != report["approved_cases"]:
        raise ValueError("Approved assessment case count differs from the reviewed bundle")
    baseline = report["human_baseline"].get(approval.baseline_key, {})
    field = {"agreement": "estimate", "cohen_kappa": "cohen_kappa"}.get(gate.baseline_statistic)
    if field is None or baseline.get(field) is None or baseline[field] != gate.baseline_value:
        raise ValueError(
            "Approved baseline must identify an actual reported agreement or cohen_kappa"
        )
    experts = {expert.name.casefold(): expert.model_dump() for expert in gate.experts}
    used = {r.reviewer_id for r in bundle.ratings if r.channel == "assessment"}
    for reviewer in bundle.reviewers:
        if reviewer.reviewer_id in used:
            actual = reviewer.model_dump(exclude={"reviewer_id"})
            if experts.get(reviewer.name.casefold()) != actual:
                raise ValueError(
                    "Every assessment reviewer needs matching appointment and training records"
                )
    evidence = approval.model_dump(mode="json", exclude={"baseline_key"})
    for name in ("false_pass", "false_incomplete"):
        metric = report["metrics"][f"assessment.{name}"]
        if not metric["denominator"] or metric["estimate"] is None:
            raise ValueError(f"{name} has no observed denominator")
        if metric["estimate"] > evidence[f"max_{name}"]:
            raise ValueError(f"{name} exceeds its explicitly approved maximum")
        evidence[name] = metric["estimate"]
    evidence["recorded_validation"] = {
        "bundle_digest": digest(bundle),
        "manifest_digest": report["manifest_digest"],
        "report_digest": digest(report),
        "baseline_key": approval.baseline_key,
        "human_baseline": baseline,
        "error_metrics": {
            name: report["metrics"][f"assessment.{name}"]
            for name in ("false_pass", "false_incomplete")
        },
        "uncertainty": report["uncertainty"],
    }
    return {
        "expected_fingerprint": fingerprint,
        "expires_at": expires_at.isoformat(),
        "evidence": evidence,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approval-schema",
        action="store_true",
        help="Print the required signed-record JSON schema",
    )
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--current-manifest", type=Path)
    parser.add_argument("--approval-record", type=Path)
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--expires-at")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    if args.approval_schema:
        print(json.dumps(ApprovalRecord.model_json_schema(), indent=2))
        return 0
    if any(
        getattr(args, name) is None
        for name in (
            "bundle",
            "current_manifest",
            "approval_record",
            "expected_fingerprint",
            "expires_at",
            "output",
        )
    ):
        parser.error(
            "All six input/output options are required unless printing the approval schema"
        )
    try:
        packet = prepare_packet(
            Bundle.model_validate_json(args.bundle.read_text(encoding="utf-8-sig")),
            Manifest.model_validate_json(args.current_manifest.read_text(encoding="utf-8-sig")),
            args.repo,
            json.loads(args.approval_record.read_text(encoding="utf-8-sig")),
            args.expected_fingerprint,
            args.expires_at,
        )
        # Never overwrite an earlier packet, including after a failed preparation.
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(json.dumps(packet, indent=2, allow_nan=False) + "\n")
    except (ValueError, OSError) as error:
        parser.exit(2, f"No packet written: {error}\n")
    print(
        "Validation packet prepared. Administrator review and separate signed release remain required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
