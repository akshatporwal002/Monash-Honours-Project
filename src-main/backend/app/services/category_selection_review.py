"""Review only deterministic selection from a currently approved curriculum.

This is not a semantic assessment of newly generated content. Teaching claims
remain covered by the referenced human approvals; empirical quality is unknown.
"""

from app.schemas.category_review import (
    CategoryAssessment,
    CategoryReviewRequest,
    DimensionFinding,
    OutputCategory,
    ReviewDimension,
    ReviewEvidence,
    ReviewProvenance,
)
from app.services.category_review import request_digest, review_output

SELECTION_POLICY = "approved-selection-review.v1"


def review_selection(decision, receipt, path):
    bindings = path.bindings if path else {}
    evidence = tuple(
        ReviewEvidence(
            reference=f"task:{identity}",
            version=binding["task_revision_id"],
            kind="approved_content",
            approval_reference=binding["review_event_id"],
            content=binding,
        )
        for identity, binding in bindings.items()
    ) + (
        ReviewEvidence(
            reference=f"progress:{receipt.workflow_id}",
            version=receipt.snapshot_id or "no-model-update",
            kind="observation",
            content={"state": receipt.state, "evidence_ids": receipt.evidence_ids},
        ),
    )
    request = CategoryReviewRequest(
        category=OutputCategory.SUGGESTION,
        course_id=receipt.course_id,
        subject_id=receipt.workflow_id,
        scope="reviewed_selection",
        output={key: decision[key] for key in ("state", "reason", "uncertainty", "options")},
        evidence=evidence,
        versions={
            "selection_policy": SELECTION_POLICY,
            "rule": decision["rule_version"],
            "pathway": path.id if path else "none",
            "model": decision["snapshot_id"] or "none",
            "preference": str(decision["preference_version"]),
        },
    )
    references = tuple(f"task:{option['task_id']}" for option in decision["options"])
    safe = (
        all(
            option["task_id"] in bindings
            and option["title"] == bindings[option["task_id"]]["title"]
            for option in decision["options"]
        )
        and decision["uncertainty"] == 1.0
    )
    reasons = {
        ReviewDimension.FACTUAL_ACCURACY: "No new teaching proposition is generated. Approved task labels are reused; their factual accuracy is not remeasured.",
        ReviewDimension.GROUNDING: "Options retain exact task revisions, source approvals and educator review events from the current pathway.",
        ReviewDimension.RELEVANCE: "The current outcome pathway and learner prerequisites determine eligible options; no learning benefit is inferred.",
        ReviewDimension.OUTCOME_ALIGNMENT: "Selection uses the approved outcome pathway; it does not alter a Bloom target or propose new task content.",
        ReviewDimension.EVIDENCE_ALIGNMENT: "The progress receipt and uncertain model reference are retained. The selection creates no criterion decision or result.",
        ReviewDimension.SUPPORT: "Only task labels and existing support levels are selected. No answer, hint or instructional content is delivered here.",
        ReviewDimension.CLARITY: "Fixed service wording identifies the next approved activity or explains why no suggestion is available; semantic usefulness is not measured.",
        ReviewDimension.ACCESSIBILITY: "The selection adds no alternate representation or access adjustment. Existing course task accessibility still requires its own review.",
        ReviewDimension.LEARNER_SAFETY: "The selection retains uncertainty and makes no proficiency, diagnosis or learning-success claim; preferences and overrides remain separate.",
        ReviewDimension.INDEPENDENCE: "Choosing an approved activity neither records independent achievement nor releases transfer instructions; stage gates remain authoritative.",
    }
    findings = tuple(
        DimensionFinding(
            dimension=dimension,
            outcome="VIOLATED"
            if not safe
            else (
                "SATISFIED"
                if dimension == ReviewDimension.GROUNDING and references
                else "NOT_APPLICABLE"
            ),
            basis="reviewed_content_inheritance"
            if dimension == ReviewDimension.GROUNDING and references and safe
            else "structural",
            reason=reasons[dimension]
            if safe
            else "The selection differs from its approved content or claims unwarranted certainty.",
            evidence_references=references if safe else (),
        )
        for dimension in ReviewDimension
    )
    record = review_output(
        request,
        lambda _: CategoryAssessment(
            request_digest=request_digest(request),
            reviewer=ReviewProvenance(
                kind="deterministic",
                reference="approved-curriculum-selector",
                version=SELECTION_POLICY,
            ),
            findings=findings,
        ),
    )
    return request, record
