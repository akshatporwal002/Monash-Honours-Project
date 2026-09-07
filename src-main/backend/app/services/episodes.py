"""Server boundaries for prediction reveal and private unaided transfer."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import TaskFormVersion
from app.models.assessment_work import AssessmentWorkStart
from app.models.episode import EpisodeCheckpoint, EpisodeStageStart
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask
from app.models.simulation import CircuitVersion, SimulationRun
from app.models.task_review import TaskRevision
from app.schemas.episode import EpisodePayloadV1, ResponseContent
from app.services.episode_contract import learner_episode_plan, validate_reviewed_episode_plan
from app.services.task_review import TaskReviewError


class EpisodeService:
    def __init__(self, session: Session):
        self.session = session

    def work_plan(self, work):
        if work is None:
            return None
        form = self.session.get(TaskFormVersion, work.task_form_version_id)
        revision = (
            self.session.get(TaskRevision, form.task_revision_id)
            if form and form.task_revision_id
            else None
        )
        frozen = (
            form.constraints.get("episode_plan")
            if form and isinstance(form.constraints, dict)
            else None
        )
        reviewed = revision.snapshot.get("marking_criteria") if revision else None
        plan = validate_reviewed_episode_plan(reviewed, frozen)
        if plan and frozen is None:
            raise TaskReviewError("The reviewed episode plan is not frozen in this form", 409)
        return plan

    def _stage(self, work, stage_id, part_id, plan):
        if stage_id is None:
            if part_id != plan.supported_part_id:
                raise TaskReviewError("Unknown supported episode part", 422)
            return None
        stage = self.session.get(EpisodeStageStart, stage_id)
        if stage is None or (
            stage.student_id,
            stage.task_id,
            stage.assessment_work_start_id,
            stage.task_form_version_id,
            stage.part_id,
        ) != (work.student_id, work.task_id, work.id, work.task_form_version_id, part_id):
            raise TaskReviewError("Transfer stage reference does not match this work", 409)
        if part_id != plan.transfer.part_id:
            raise TaskReviewError("Unknown transfer episode part", 422)
        return stage

    def validate_response(
        self, work, episode, content, *, submitting=False, student_id=None, task_id=None
    ):
        plan = self.work_plan(work)
        if plan and episode is None:
            raise TaskReviewError("This task requires its learning episode response", 422)
        if episode is None:
            return
        stages = [
            (episode.supported, content, None, plan.supported_part_id if plan else "supported")
        ]
        if episode.transfer:
            if plan is None or work is None:
                raise TaskReviewError("No approved transfer stage exists for this task", 422)
            transfer = episode.transfer
            self._stage(work, transfer.stage_start_id, transfer.part_id, plan)
            stages.append(
                (transfer.process, transfer.content, transfer.stage_start_id, transfer.part_id)
            )
        for process, current, stage_id, part_id in stages:
            if process.prediction_checkpoint_id:
                if work is None:
                    raise TaskReviewError("Prediction checkpoint has no assessment work", 422)
                checkpoint = self.session.get(EpisodeCheckpoint, process.prediction_checkpoint_id)
                if checkpoint is None or (
                    checkpoint.student_id,
                    checkpoint.task_id,
                    checkpoint.assessment_work_start_id,
                    checkpoint.stage_start_id,
                    checkpoint.part_id,
                ) != (work.student_id, work.task_id, work.id, stage_id, part_id):
                    raise TaskReviewError(
                        "Prediction checkpoint does not match this work and stage", 409
                    )
                if checkpoint.prediction != (
                    process.prediction.model_dump(mode="json") if process.prediction else None
                ):
                    raise TaskReviewError(
                        "Original prediction is immutable; create a new checkpoint for changed input",
                        422,
                    )
                if checkpoint.input_content != current.model_dump(mode="json"):
                    raise TaskReviewError(
                        "Prediction checkpoint input has changed; record a new prediction for this input",
                        422,
                    )
            if process.revision:
                earlier = self.session.get(
                    SubmissionAttempt, process.revision.previous_response_version_id
                )
                if (
                    earlier is None
                    or earlier.student_id != (work.student_id if work else student_id)
                    or earlier.task_id != (work.task_id if work else task_id)
                    or earlier.assessment_work_start_id != (work.id if work else None)
                ):
                    raise TaskReviewError(
                        "Revision must reference your earlier response to this task and work", 422
                    )
                if stage_id and (
                    not earlier.episode
                    or not earlier.episode.get("transfer")
                    or earlier.episode["transfer"]["stage_start_id"] != stage_id
                ):
                    raise TaskReviewError("Revision references a different transfer stage", 422)
            for reference in process.simulation_references:
                run = self.session.get(SimulationRun, reference.run_id)
                circuit = self.session.get(CircuitVersion, reference.circuit_version_id)
                if (
                    run is None
                    or circuit is None
                    or run.circuit_version_id != circuit.id
                    or run.owner_id != (work.student_id if work else student_id)
                    or circuit.task_id != (work.task_id if work else task_id)
                    or circuit.owner_id != run.owner_id
                    or (work and circuit.course_id != work.course_id)
                ):
                    raise TaskReviewError(
                        "Simulation reference does not match this learner and task", 422
                    )
                if (
                    circuit.circuit != self.circuit_input(current.circuit)
                    or run.prediction_checkpoint_id != process.prediction_checkpoint_id
                    or run.episode_stage_start_id != stage_id
                    or run.shots != (current.circuit or {}).get("shots", 1024)
                    or run.seed != (current.circuit or {}).get("seed", 42)
                ):
                    raise TaskReviewError(
                        "Simulation reference does not match this response input and stage", 422
                    )
        if submitting and plan:
            self._required(episode.supported, plan.required_responses)
            if plan.prediction_required and not episode.supported.prediction_checkpoint_id:
                raise TaskReviewError("Record the prediction before submitting", 422)
            if episode.transfer is None or not self.has_content(episode.transfer.content):
                raise TaskReviewError("Complete the fresh application before submitting", 422)

    @staticmethod
    def has_content(content):
        return bool(
            content.answer.strip() or (content.code and content.code.strip()) or content.circuit
        )

    @staticmethod
    def _required(process, names):
        for name in names:
            value = getattr(process, name)
            present = (
                EpisodeService.has_content(value)
                if isinstance(value, ResponseContent)
                else bool(value and value.strip())
            )
            if not present:
                raise TaskReviewError(f"Complete {name} before continuing", 422)

    @staticmethod
    def circuit_input(circuit):
        if not circuit:
            return None
        return {"qubits": circuit.get("qubits"), "operations": circuit.get("operations", [])}

    def checkpoint(self, draft, *, part_id, stage_start_id=None):
        work = self.session.get(AssessmentWorkStart, draft.assessment_work_start_id)
        plan = self.work_plan(work)
        if plan is None:
            raise TaskReviewError("This task has no approved prediction stage", 422)
        self._stage(work, stage_start_id, part_id, plan)
        episode = EpisodePayloadV1.model_validate(draft.episode)
        current = ResponseContent(answer=draft.answer, code=draft.code, circuit=draft.circuit)
        process = episode.supported
        if stage_start_id:
            if not episode.transfer or episode.transfer.stage_start_id != stage_start_id:
                raise TaskReviewError(
                    "Save the transfer response before recording its prediction", 422
                )
            current, process = episode.transfer.content, episode.transfer.process
        self._required(process, ("prediction",))
        prediction = process.prediction.model_dump(mode="json")
        inputs = current.model_dump(mode="json")
        if process.prediction_checkpoint_id:
            old = self.session.get(EpisodeCheckpoint, process.prediction_checkpoint_id)
            if old and old.prediction == prediction and old.input_content == inputs:
                return old
        checkpoint = EpisodeCheckpoint(
            student_id=work.student_id,
            task_id=work.task_id,
            assessment_work_start_id=work.id,
            task_form_version_id=work.task_form_version_id,
            stage_start_id=stage_start_id,
            part_id=part_id,
            prediction=prediction,
            input_content=inputs,
            snapshot=episode.model_dump(mode="json"),
        )
        self.session.add(checkpoint)
        self.session.flush()
        updated = episode.model_dump(mode="json")
        target = updated["transfer"]["process"] if stage_start_id else updated["supported"]
        target["prediction_checkpoint_id"] = checkpoint.id
        draft.episode = updated
        self.session.flush()
        return checkpoint

    def start_transfer(self, draft):
        work = self.session.get(AssessmentWorkStart, draft.assessment_work_start_id)
        plan = self.work_plan(work)
        if plan is None:
            raise TaskReviewError("No approved fresh application exists", 422)
        existing = self.session.scalar(
            select(EpisodeStageStart).where(EpisodeStageStart.assessment_work_start_id == work.id)
        )
        if existing:
            return existing
        episode = EpisodePayloadV1.model_validate(draft.episode)
        self._required(episode.supported, plan.required_responses)
        if plan.prediction_required and not episode.supported.prediction_checkpoint_id:
            raise TaskReviewError("Record the supported prediction before transfer", 422)
        stage = EpisodeStageStart(
            student_id=work.student_id,
            task_id=work.task_id,
            assessment_work_start_id=work.id,
            task_form_version_id=work.task_form_version_id,
            part_id=plan.transfer.part_id,
            supported_snapshot={
                "content": ResponseContent(
                    answer=draft.answer, code=draft.code, circuit=draft.circuit
                ).model_dump(mode="json"),
                "process": episode.supported.model_dump(mode="json"),
            },
        )
        self.session.add(stage)
        self.session.flush()
        return stage

    def state(self, draft):
        work = (
            self.session.get(AssessmentWorkStart, draft.assessment_work_start_id)
            if draft.assessment_work_start_id
            else None
        )
        plan = self.work_plan(work)
        if plan is None:
            return None
        stage = self.session.scalar(
            select(EpisodeStageStart).where(EpisodeStageStart.assessment_work_start_id == work.id)
        )
        projection = learner_episode_plan(plan)
        projection["supported_hints"] = [
            f"Conceptual hint {index + 1}" for index in range(len(plan.supported_hints))
        ]
        if stage:
            projection["supported_hints"] = []
            projection["transfer"] = {
                "stage_start_id": stage.id,
                "part_id": stage.part_id,
                "prompt": plan.transfer.prompt,
                "instructions": plan.transfer.instructions,
                "starter_code": plan.transfer.starter_code,
                "starter_circuit": deepcopy(plan.transfer.starter_circuit),
            }
        else:
            projection["transfer"] = None
        return projection

    def require_simulation_checkpoint(
        self,
        *,
        owner_id,
        task_id,
        checkpoint_id,
        stage_start_id,
        part_id,
        circuit,
        shots=1024,
        seed=42,
    ):
        work = self.session.scalar(
            select(AssessmentWorkStart).where(
                AssessmentWorkStart.student_id == owner_id, AssessmentWorkStart.task_id == task_id
            )
        )
        plan = self.work_plan(work)
        task = self.session.get(LearningTask, task_id)
        if (
            work is None
            and task
            and isinstance(task.marking_criteria, dict)
            and task.marking_criteria.get("episode_plan")
        ):
            raise TaskReviewError("Start the approved episode and record a prediction first", 422)
        if plan is None:
            if checkpoint_id or stage_start_id:
                raise TaskReviewError("This task has no prediction checkpoint", 422)
            return
        self._stage(work, stage_start_id, part_id or plan.supported_part_id, plan)
        if not plan.prediction_required:
            return
        checkpoint = self.session.get(EpisodeCheckpoint, checkpoint_id) if checkpoint_id else None
        if (
            checkpoint is None
            or (
                checkpoint.student_id,
                checkpoint.task_id,
                checkpoint.assessment_work_start_id,
                checkpoint.stage_start_id,
            )
            != (owner_id, task_id, work.id, stage_start_id)
            or self.circuit_input(checkpoint.input_content.get("circuit")) != circuit
            or (checkpoint.input_content.get("circuit") or {}).get("shots", 1024) != shots
            or (checkpoint.input_content.get("circuit") or {}).get("seed", 42) != seed
        ):
            raise TaskReviewError(
                "Record a prediction for this exact circuit before viewing results", 422
            )

    def require_run_reveal(self, run, circuit):
        self.require_simulation_checkpoint(
            owner_id=run.owner_id,
            task_id=circuit.task_id,
            checkpoint_id=run.prediction_checkpoint_id,
            stage_start_id=run.episode_stage_start_id,
            part_id=None
            if run.episode_stage_start_id is None
            else self.session.get(EpisodeStageStart, run.episode_stage_start_id).part_id,
            circuit=circuit.circuit,
            shots=run.shots,
            seed=run.seed,
        )
