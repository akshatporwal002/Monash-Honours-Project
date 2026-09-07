# Task 11: simulation evidence and execution limits

Status: implemented and locally verified.

Branch: `feat/task-11-durable-simulation-evidence`.
Base: Task 10 merge `7fe68f77776018b972441f0988a39b68e3fb1cb9`.

## Execution and evidence

Qiskit runs in a separate Python process with a 15-second budget, including slot waiting.
Each API process permits two concurrent simulations. Each Aer execution uses one native thread.
The parent kills and reaps a timed-out child before releasing its slot.
Supported circuits use H, X, and CX, one to five qubits, one to 4,096 shots, and at most 30 operations.
The same validator protects API simulation, saved submissions, and feedback execution.
It rejects Boolean and fractional indices instead of coercing them.

Every actual application run saves its request before execution and its terminal evidence before returning a successful result.
Three append-only tables preserve circuit versions, execution requests, and terminal outcomes.
Circuit versions include the owner, task, course, canonical circuit, and SHA-256 digest.
Requests include the seed, shots, policy version, engine versions, purpose, submission reference, and timestamps.
Successful outcomes retain counts, exact probabilities, sampled frequencies, amplitudes, qubit order, and measurement mapping.
Failed outcomes retain a safe code and contain no result payload.

The task handler validates structure without executing an unrecorded simulation.
Its legacy gate-assembly check reports gate presence only; formal assessment uses the separate assessment path.
The unmounted legacy simulation route returns 410. Its stateless execution wrapper has been removed.

## API, feedback, and recovery

`POST /students/me/simulate` returns a saved run with an explicit status and nullable result.
A supplied task must be accessible, unlocked, and support circuits. Requests without a task are recorded as private practice.
A repeated request key with identical inputs returns the original run. Changed inputs using that key return 409.
Concurrent requests cannot claim the same execution twice.
`GET /simulations/{run_id}` enforces learner ownership and current course access.
Course educators and administrators can read course-scoped runs; private practice remains private.
`GET /students/me/tasks/{task_id}/simulations` returns bounded, newest-first task history for its learner.
`GET /simulations/capabilities` exposes the supported execution policy to authenticated callers.

The task workspace sends its task ID and a request key.
It displays exact probabilities separately from sampled frequencies and labels the saved run.
Starting another run clears the previous displayed result. A failed run shows its saved failure state.

Feedback validates the stored submission's learner, task, and course before using its circuit.
It saves the run against that immutable submission and uses the real run ID in feedback context.
Replay reuses the saved run for the same submission, execution policy, and engine versions.
The submission's seed and shots are retained. A failed simulation cannot become completed feedback evidence.

A run without terminal evidence remains pending until its recovery deadline, 20 seconds after creation.
The deadline includes the 15-second execution budget and five seconds for recording completion.
The database worker marks expired requests as interrupted in bounded batches. Reading an expired run also records interruption.
A late result cannot replace terminal evidence. Recovery never invents counts or silently reruns a failed request.
A new request key records an explicit new attempt.

## Migration and rollback

Migration `20260907_0025` creates the evidence tables and SQLite mutation and replacement guards.
ORM guards also reject changes and deletion. Upgrade replay preserves existing evidence and recreates missing guards.
Readiness requires this migration head. Existing historical simulations are not backfilled with invented settings or outputs.
A populated simulation archive blocks downgrade before any destructive DDL.
Earlier source, assessment, review, and material-processing protections also run before downgrade.
Use a verified backup for recovery when protected history prevents rollback.

## Verification

Focused circuit execution checks: 12 passed, including actual child timeout cleanup and phase-sensitive state evidence.
Simulation storage, task validation, and migration checks: 55 passed before the final feedback-seed regression.
The final feedback-seed and storage checks passed all 18 tests.
The final full backend pass completed 782 tests with 85.52% service coverage.
This includes the final feedback-seed change and all migration and worker checks.
The migration test covers replay over populated evidence, schema drift, mutation rejection, and protected downgrade.
API checks cover course access, locked tasks, invalid inputs, saved history, and request replay.
Feedback checks cover persisted run references, replay, and mismatched learner rejection.

Frontend: 180 tests passed in 52 files. Lint and production build passed.
The new interface test checks exact versus sampled values and removal of stale output after a saved timeout.
The first frontend run exposed a generic error-message issue; the fixed complete suite passed.
The build retains its existing large-chunk warning, with the main bundle now about 648 KB before gzip.
OpenAPI and TypeScript contracts were regenerated, and both drift checks passed.
Ruff lint and formatting checks passed for 325 files.

Installed versions verified locally: Qiskit 2.5.1 and Qiskit Aer 0.17.2.
Reproducibility is checked by running again from the saved circuit, seed, and shots.
Matching results across different future engine versions are not assumed.
This task does not activate an assessment policy, validate AI suggestions, or prove production load and fault recovery.
Task 12 consumes the capability policy. Task 15 must choose evidence suited to each approved criterion.
Tasks 36 through 39 retain their complete integration, operational, performance, and usability gates.

## Reference basis

Qiskit's displayed bitstrings place the highest-index qubit on the left and qubit zero on the right.
The circuit's qubit indices and classical measurement mapping must therefore be retained explicitly.
See [IBM's bit-ordering guide](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering).

The runner reads exact probabilities and amplitudes before measurement, then executes seeded Aer sampling.
The [Statevector API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Statevector)
and [AerSimulator API](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html)
describe those operations and execution options. Local tests verify them against the installed versions.
The documentation pages can describe different patch versions; they do not replace the pinned-runtime checks.

Equal measurement probabilities do not establish equal quantum states.
The plus/minus-state regression retains their distinct relative phases despite equal measurement probabilities.
Task 15 must use evidence suited to each approved criterion rather than treating distribution agreement as universal proof.
