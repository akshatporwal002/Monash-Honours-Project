"""Resolve frozen learner and simulation evidence without changing source records."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from typing import Any

from sqlalchemy.orm import Session

from app.models.assessment import AssessmentAttempt
from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun
from app.schemas.assessment import (
    AssessmentVersionReference,
    EvidenceReference,
    InvalidEvidenceReference,
    MissingEvidenceReference,
    ResolvedEvidenceReference,
)
from app.schemas.episode import FrozenResponseRead
from app.services.episode_contract import (
    FrozenResponseInvalid,
    FrozenResponseMissing,
    FrozenResponseReader,
    FrozenResponseStale,
)


class ResponseEvidenceResolver:
    def __init__(self, reader: FrozenResponseReader, session: Session) -> None:
        self.reader = reader
        self.session = session

    def resolve(self, *, assessment: AssessmentVersionReference, evidence_id: str):
        try:
            response = self.reader.read(assessment=assessment)
            if evidence_id == response.reference.evidence_id:
                return ResolvedEvidenceReference(reference=response.reference)
            simulation = self.simulation(assessment, response, evidence_id)
            if simulation is None or simulation["status"] != "completed":
                return MissingEvidenceReference(
                    assessment=assessment,
                    evidence_id=evidence_id,
                    reason_code="SIMULATION_UNAVAILABLE",
                )
            run = self.session.get(SimulationRun, evidence_id)
            occurred = (
                run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=UTC)
            )
            digest = hashlib.sha256(
                json.dumps(simulation, sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            return ResolvedEvidenceReference(
                reference=EvidenceReference(
                    assessment=assessment,
                    evidence_id=evidence_id,
                    evidence_type="simulation_output",
                    schema_version="assessment.simulation.v1",
                    record_version=1,
                    content_digest=f"sha256:{digest}",
                    source_record_id=evidence_id,
                    source_record_version=1,
                    occurred_at=occurred,
                )
            )
        except FrozenResponseMissing:
            return MissingEvidenceReference(
                assessment=assessment, evidence_id=evidence_id, reason_code="RESPONSE_MISSING"
            )
        except FrozenResponseStale:
            # No trusted reference is available to populate STALE.reference.
            return InvalidEvidenceReference(reference_id=evidence_id, reason_code="RESPONSE_STALE")
        except FrozenResponseInvalid:
            return InvalidEvidenceReference(
                reference_id=evidence_id, reason_code="RESPONSE_INVALID"
            )

    def simulations(
        self, assessment: AssessmentVersionReference, response: FrozenResponseRead
    ) -> tuple[dict[str, Any], ...]:
        ids = self._simulation_ids(response)
        return tuple(self.simulation(assessment, response, run_id) for run_id in ids)

    @staticmethod
    def _simulation_ids(
        response: FrozenResponseRead,
    ) -> dict[str, tuple[str, str | None, str | None]]:
        if response.episode is None:
            return {}
        stages = [(response.episode.supported, None)]
        if response.episode.transfer is not None:
            stages.append(
                (response.episode.transfer.process, response.episode.transfer.stage_start_id)
            )
        values = {}
        for stage, stage_start_id in stages:
            for item in stage.simulation_references:
                expected = (item.circuit_version_id, stage.prediction_checkpoint_id, stage_start_id)
                if item.run_id in values and values[item.run_id] != expected:
                    raise FrozenResponseInvalid(
                        "A simulation cannot supply incompatible stage evidence"
                    )
                values[item.run_id] = expected
        return values

    def simulation(
        self, assessment: AssessmentVersionReference, response: FrozenResponseRead, run_id: str
    ) -> dict[str, Any] | None:
        expected = self._simulation_ids(response).get(run_id)
        if expected is None:
            return None
        run = self.session.get(SimulationRun, run_id)
        circuit_id, checkpoint_id, stage_start_id = expected
        circuit = self.session.get(CircuitVersion, circuit_id)
        attempt = self.session.get(AssessmentAttempt, assessment.assessment_attempt_id)
        if run is None or circuit is None or attempt is None:
            raise FrozenResponseMissing("Referenced simulation evidence is unavailable")
        if (
            run.circuit_version_id != circuit_id
            or run.prediction_checkpoint_id != checkpoint_id
            or run.episode_stage_start_id != stage_start_id
            or run.owner_id != attempt.student_id
            or circuit.owner_id != attempt.student_id
            or circuit.course_id != assessment.course_id
            or circuit.task_id != assessment.task_id
            or (
                run.submission_id is not None
                and run.submission_id != assessment.response_version_id
            )
        ):
            raise FrozenResponseInvalid(
                "Referenced simulation evidence does not match the frozen response"
            )
        digest = hashlib.sha256(
            json.dumps(circuit.circuit, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if circuit.content_digest != digest:
            raise FrozenResponseStale("Referenced circuit digest is stale")
        from app.services.episodes import EpisodeService

        content = response.content
        if stage_start_id is not None:
            if response.episode is None or response.episode.transfer is None:
                raise FrozenResponseInvalid("The simulation has no matching transfer response")
            content = response.episode.transfer.content
        if circuit.circuit != EpisodeService.circuit_input(content.circuit):
            raise FrozenResponseInvalid("The simulation circuit differs from the submitted stage")
        outcome = self.session.get(SimulationOutcome, run_id)
        return {
            "run_id": run.id,
            "circuit_version_id": circuit.id,
            "prediction_checkpoint_id": run.prediction_checkpoint_id,
            "episode_stage_start_id": run.episode_stage_start_id,
            "circuit": circuit.circuit,
            "shots": run.shots,
            "seed": run.seed,
            "policy_version": run.policy_version,
            "engine_versions": run.engine_versions,
            "created_at": run.created_at,
            "deadline_at": run.deadline_at,
            "finished_at": outcome.created_at if outcome else None,
            "status": outcome.status if outcome else "pending",
            "result": outcome.result if outcome else None,
            "error_code": outcome.error_code if outcome else None,
        }
