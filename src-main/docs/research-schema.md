# Research measurement schema

Research is disabled unless an injected eligibility policy confirms consent and course
eligibility. The workflow UUID is the shared case ID. Each eligible terminal workflow creates one
completed agentic record and one pending baseline record only after student feedback is durable.

## Measurement identity and state

- `case_id`, workflow reference, pseudonymous actor and submission references.
- Course, task, task type, experimental condition, and measurement schema version.
- Provider/model/prompt version and created/completed UTC timestamps.
- `pending`, `running`, `completed`, or `failed` status.
- Fenced execution token, 300-second lease, processing-attempt count, and sanitized failure
  category.
- Fallback, comparability, and usage-completeness flags.

## Inputs and outcomes

Research records may retain source IDs, display labels, and relevance scores, but never retrieved
chunks. They may retain simulation reference/status, generated structured output, and structured
judge results, but never the prompt, transient student answer, or raw provider errors.

Normalized measurement fields include retrieval request/hit counts, first and final evaluation
status/decision, correctness/relevance/grounding/actionability/safety scores, unsupported-claim
count, quality-policy version, primary latency, token usage, and cost. Evaluation-only latency,
usage, and cost remain separate for the baseline.

Legacy rows are marked `legacy-v1`, measurement-incomplete, and conservatively non-comparable.

## Conditions

- `agentic_rag`: the complete student-facing pipeline. Primary latency/cost includes context,
  generation, judging, any regeneration, and fallback decision.
- `single_step_baseline`: exactly one `baseline-v1` generation and one measurement-only judge call.
  The generation context contains task information, criteria/expected answer, and the transient
  answer only. Retrieval, simulation, earlier feedback, judge guidance, and regeneration are
  forbidden. Generation uses the agentic provider/base model and empty source/simulation
  references. Its primary measurement covers generation only; judge usage is separate.

The baseline never changes or delays released student feedback. Expired jobs can be reclaimed with
a new fenced token up to three total claims; an expired third claim becomes a terminal sanitized
failure. Ordinary provider retries are not performed inside a claim.
