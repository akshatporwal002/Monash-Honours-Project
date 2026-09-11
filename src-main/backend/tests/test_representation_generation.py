"""Generated alternatives remain source-grounded drafts and preserve frozen access."""

import asyncio
import json
from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from support.alignment import next_action_contract
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo
from test_multipart_generation import generated
from test_practice_representations import command
from test_practice_representations import content as content
from test_practice_representations import context as context
from test_task14_lifecycle import complete

from app.api.dependencies.authentication import get_current_user
from app.api.routes import practice_representations as representation_routes
from app.api.routes.assessment import _definition_draft
from app.db.session import get_db
from app.main import create_app
from app.models import TaskType, UserRole
from app.models.assessment import TaskFormVersion
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, CourseState, Enrollment
from app.schemas.episode import EpisodeHelpUseWrite
from app.schemas.feedback import TokenUsage
from app.schemas.lms import SubmissionCreate
from app.schemas.representation_generation import RepresentationGenerationWrite
from app.services.assessment.definitions import AssessmentDefinitionService
from app.services.assessment.generated_design import generated_assessment_draft
from app.services.evidence.live import evidence_id
from app.services.feedback.contracts import StructuredLlmResponse
from app.services.lms import LmsService
from app.services.provider_usage import ProviderBudgetError
from app.services.representation_drafts import RepresentationDraftService
from app.services.representation_generation import (
    attach_generated_task_representations,
    bind_task_representation_sources,
    local_representation_candidates,
    validate_generated_representations,
)
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_generation_hooks_bind_installed_content_and_source_quotes_without_aliasing():
    original = {
        "prompt": "Explain X.",
        "instructions": "Use the source.",
        "source_references": ["chunk"],
        "marking_criteria": {"generation_design": {"equivalent_formats": []}},
    }
    source = {"chunk_id": "chunk", "text": "X exchanges the computational basis states."}
    task = attach_generated_task_representations(original, [source])
    assert "practice_representations" not in original["marking_criteria"]
    assert "text" in task["marking_criteria"]["generation_design"]["equivalent_formats"]
    bound = bind_task_representation_sources(task["marking_criteria"], {"chunk": "passage"})
    assert all(
        item["source_references"] == ["passage"] for item in bound["practice_representations"]
    )
    generation = bound["representation_generation"]["practice"]
    assert all(
        item["source_references"] == ["passage"] for item in generation["installed"]["practice"]
    )
    assert all(
        quote["source_reference"] == "passage"
        for item in generation["candidate"]["variants"]
        for quote in item["source_quotes"]
    )
    assert task["marking_criteria"]["practice_representations"][0]["source_references"] == ["chunk"]


@pytest.mark.parametrize("failure", ["foreign_quote", "changed_task", "transfer_instruction"])
def test_configured_generation_rechecks_output_and_task_before_saving(db_session, context, failure):
    _, owner, _, task, _ = context
    if failure == "transfer_instruction":
        task, owner = generated(db_session)
    review = TaskReviewService(db_session)
    revision = review.latest_revision(task.id)
    original = deepcopy(task.marking_criteria)

    class Client:
        async def generate_structured(self, request):
            payload = json.loads(request.user_prompt)
            assert "expected_answer" not in payload["task"]
            assert "solution" not in payload["task"]["marking_criteria"]
            candidate = local_representation_candidates(
                payload["task"], payload["sources"]
            ).model_dump(mode="json")
            if failure == "foreign_quote":
                candidate["variants"][0]["source_quotes"][0]["quote"] = "Fabricated source claim"
            if failure == "changed_task":
                task.instructions += " Changed during generation."
                db_session.commit()
                review.capture(task, actor_user_id=owner.id)
                db_session.commit()
            return StructuredLlmResponse(
                output=candidate,
                provider="synthetic",
                model="synthetic",
                token_usage=TokenUsage(),
                estimated_cost=Decimal("0"),
            )

    with pytest.raises((ValueError, TaskReviewError)):
        asyncio.run(
            RepresentationDraftService(db_session, Client()).generate(
                owner,
                task.id,
                RepresentationGenerationWrite(
                    expected_revision_id=revision.id,
                    target="transfer" if failure == "transfer_instruction" else "practice",
                ),
            )
        )
    db_session.refresh(task)
    assert task.marking_criteria == original


def test_source_aware_local_builder_covers_permitted_formats_and_preserves_access_input():
    task = {
        "prompt": "Trace the supplied circuit.",
        "instructions": "Explain the input and output.",
        "source_references": ["source"],
        "expected_answer": "PRIVATE ANSWER",
        "marking_criteria": {
            "starter_circuit": {"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]}
        },
    }
    source = "Worked example: apply X to |0>. X exchanges the basis states, so the output is |1>."
    candidate = local_representation_candidates(task, [{"chunk_id": "source", "text": source}])
    assert {item.mode for item in candidate.variants} == {
        "text",
        "visual",
        "worked_example",
        "circuit",
        "stepwise",
    }
    assert all(quote.quote in source for item in candidate.variants for quote in item.source_quotes)
    assert "PRIVATE ANSWER" not in candidate.model_dump_json()
    instruction = [
        item
        for item in candidate.variants
        if item.mode == "text" and item.support_kind == "instructional"
    ]
    assert instruction[0].text != instruction[1].text
    assert (
        next(
            item for item in candidate.variants if item.mode == "worked_example"
        ).instructional_support_level
        == 4
    )
    access = local_representation_candidates(
        task, [{"chunk_id": "source", "text": source}], access_only=True
    )
    assert all(item.instructional_support_level == 0 for item in access.variants)
    assert (
        next(item for item in access.variants if item.mode == "circuit").reviewed_content()[
            "circuit"
        ]
        == task["marking_criteria"]["starter_circuit"]
    )
    assert any(item.mode == "worked_example" for item in access.unavailable_modes)
    assert source not in " ".join(item.text for item in access.variants)


def test_standalone_transfer_practice_offers_only_approved_access(db_session, context):
    _, _, learner, task, service = context
    task.task_type = TaskType.TRANSFER
    db_session.commit()
    approve_fixture_task(db_session, task)
    catalog = service.catalog(learner, task.id)
    assert {item.support_kind for item in catalog.choices} == {"accessibility"}
    receipt = service.deliver(
        learner, task.id, command(catalog, "access", "transfer-access", "override")
    )
    assert receipt.representation.instructional_support_level == 0
    with pytest.raises(TaskReviewError):
        service.deliver(
            learner, task.id, command(catalog, "steps", "transfer-instruction", "override")
        )


@pytest.mark.parametrize("damage", ["quote", "foreign", "access", "approval"])
def test_generated_drafts_reject_fabricated_grounding_and_support(damage):
    task = {
        "prompt": "Explain X.",
        "instructions": "Use the source.",
        "source_references": ["source"],
    }
    source = "X exchanges the computational basis states."
    candidate = local_representation_candidates(
        task, [{"chunk_id": "source", "text": source}]
    ).model_dump(mode="json")
    if damage == "quote":
        candidate["variants"][0]["source_quotes"][0]["quote"] = "Invented relationship"
    elif damage == "foreign":
        candidate["variants"][0]["source_references"] = ["foreign"]
        candidate["variants"][0]["source_quotes"][0]["source_reference"] = "foreign"
    elif damage == "access":
        candidate["variants"][0]["support_kind"] = "accessibility"
    else:
        candidate["status"] = "APPROVED"
    with pytest.raises(ValueError):
        validate_generated_representations(candidate, {"source": source}, ["source"])


def test_generation_api_saves_new_draft_without_approval_and_reuses_explicit_delivery(
    db_session, context, monkeypatch
):
    _, owner, learner, task, delivery = context
    review = TaskReviewService(db_session)
    old = review.latest_revision(task.id)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    path = f"/api/v1/practice-representations/tasks/{task.id}/generate"
    try:
        with TestClient(app) as client:
            payload = {"expected_revision_id": old.id, "target": "practice"}

            def unavailable_budget(session):
                raise ProviderBudgetError("No approved budget")

            with monkeypatch.context() as patch:
                patch.setattr(
                    representation_routes, "configured_representation_client", unavailable_budget
                )
                blocked = client.post(path, json=payload)
                assert blocked.status_code == 503
                assert review.latest_revision(task.id).id == old.id
            result = client.post(path, json=payload)
            assert result.status_code == 200, result.text
            saved = result.json()
            assert saved["revision_id"] != old.id
            assert saved["candidate"]["status"] == "DRAFT"
            assert review.latest_event(saved["revision_id"]) is None
            assert review.latest_event(old.id).state == "APPROVED"
            assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 0
            assert {"brief", "steps", "access"} <= {
                item["representation_id"]
                for item in task.marking_criteria["practice_representations"]
            }
            assert client.post(path, json=payload).status_code == 409
            app.dependency_overrides[get_current_user] = lambda: learner
            assert (
                client.post(
                    path, json={**payload, "expected_revision_id": saved["revision_id"]}
                ).status_code
                == 403
            )
            with pytest.raises(TaskReviewError):
                delivery.catalog(learner, task.id)
            approve_fixture_task(db_session, task)
            catalog = delivery.catalog(learner, task.id)
            receipt = delivery.deliver(
                learner,
                task.id,
                command(catalog, "source-stepwise-detailed", "generated", "override"),
            )
            assert receipt.representation.steps
            assert receipt.revision_id == saved["revision_id"]
            metadata = task.marking_criteria["representation_generation"]["practice"]
            assert metadata["input_revision_id"] == old.id and metadata["source_approvals"]
    finally:
        app.dependency_overrides.clear()


def test_generated_stage_access_is_private_until_entry_and_stays_level_zero(db_session):
    task, owner = generated(db_session)
    review = TaskReviewService(db_session)
    service = RepresentationDraftService(db_session)
    for target in ("supported", "transfer"):
        asyncio.run(
            service.generate(
                owner,
                task.id,
                RepresentationGenerationWrite(
                    expected_revision_id=review.latest_revision(task.id).id, target=target
                ),
            )
        )
    approve_fixture_task(db_session, task)
    _, proposal = generated_assessment_draft(
        db_session, owner, task.course_id, task.id, review.latest_revision(task.id).id
    )
    raw = proposal.model_dump(mode="json")
    raw.update(
        formal_result_eligible=True,
        next_action_contract=next_action_contract(
            *(item["stable_key"] for item in raw["criteria"])
        ),
        access_conditions={"modes": [{"mode": "text", "preserves_construct": True}]},
    )
    raw["task_forms"][0]["constraints"]["elicited_bloom_processes"] = ["APPLY"]
    lms = LmsService(db_session)
    outcome = lms.create_assessment_outcome_version(owner, task.course_id, task.learning_outcome_id)
    definitions = AssessmentDefinitionService(db_session)
    definition = definitions.create_draft(
        course_id=task.course_id,
        learning_outcome_id=task.learning_outcome_id,
        actor_user_id=owner.id,
        draft=_definition_draft(type(proposal).model_validate(raw), outcome.id),
    )
    definitions.approve(
        course_id=task.course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner.id,
        approval_reason="Explicit synthetic access and assessment review",
    )
    form = db_session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    users, _ = bootstrap_reviewed_demo(db_session)
    learner = next(user for user in users if user.role is UserRole.STUDENT)
    db_session.get(Course, task.course_id).state = CourseState.PUBLISHED
    db_session.add(Enrollment(course_id=task.course_id, student_id=learner.id))
    db_session.commit()
    assert "|1>" not in lms.get_student_task(learner, task.id).model_dump_json()
    started = lms.start_assessment_work(learner, task.id, form.id)
    state = lms.episode_state(learner, task.id)
    access_index = next(
        item["item_index"]
        for item in state["access_representation_choices"]
        if item["mode"] == "circuit"
    )
    before = EpisodeHelpUseWrite(
        assessment_work_start_id=started.assessment_work_start_id,
        kind="accessibility",
        item_index=access_index,
        request_key="supported-access",
    )
    original = lms.episode_help_use(learner, task.id, before)
    assert original["representation"]["circuit"]["operations"] == []
    payload = complete(lms, learner, task, started)
    transfer_state = lms.episode_state(learner, task.id)
    assert transfer_state["representation_choices"] == []
    index = next(
        item["item_index"]
        for item in transfer_state["access_representation_choices"]
        if item["mode"] == "circuit"
    )
    receipt = lms.episode_help_use(
        learner,
        task.id,
        EpisodeHelpUseWrite(
            assessment_work_start_id=started.assessment_work_start_id,
            stage_start_id=payload.episode.transfer.stage_start_id,
            kind="accessibility",
            item_index=index,
            request_key="transfer-access",
        ),
    )
    assert receipt["representation"]["instructional_support_level"] == 0
    assert receipt["representation"]["circuit"]["operations"] == [{"gate": "x", "targets": [0]}]
    assert (
        lms.episode_help_use(learner, task.id, before)["representation"]
        == original["representation"]
    )
    response = lms.submit(
        learner,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="complete-access"),
    )
    evidence = db_session.get(LearningEvidence, evidence_id(response.id, "transfer"))
    assert evidence.instructional_support_level == 0
    assert evidence.access_support_state.value == "PROVIDED"
