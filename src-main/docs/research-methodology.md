# Research methodology

## Study boundary

The unit of comparison is an eligible terminal feedback workflow. Eligibility is evaluated by an
injected consent/course policy and defaults to disabled. The workflow UUID groups a paired
`agentic_rag` and `single_step_baseline` condition. Student-facing feedback is persisted before
baseline work is scheduled, so measurement cannot delay or alter the learning experience.

The baseline uses the same provider and base model as agentic generation. Its `baseline-v1`
context is limited to task information, marking criteria/expected answer, and the transient answer.
It has no retrieval, simulation, previous feedback, judge guidance, or regeneration. It performs
one generation and one evaluation-only judge call. Automation uses deterministic fakes and never
contacts a real provider.

## Quality policy

`quality-policy-v1` passes only when the model reports pass, correctness/relevance/grounding/
actionability are each at least 80, safety is 100, and unsupported-claim count is zero. Agentic
first and final decisions are retained. The effective decision is recomputed at schema, pipeline,
and persistence-replay boundaries, so a custom adapter or corrupted row cannot claim a policy pass.
Baseline judging is measurement-only.

## Metrics

All filters use UTC half-open ranges. The default range is 30 days and maximum is 365. Undefined
metrics are `null` with denominator zero. P95 uses nearest rank. Every result includes schema
version, filters, units, numerator, denominator, sample size, generated timestamp, and
excluded/incomplete counts.

- Hallucination rate: valid final judged outputs with unsupported claims / valid final judged
  outputs.
- First-pass rate: first-attempt agentic passes / eligible agentic cases.
- Regeneration success: final passes among regenerated cases / all regenerated cases.
- Overall pass: final effective passes / eligible cases, separately by condition.
- Average relevance: valid final relevance scores.
- Retrieval hit rate: hits with relevance at least 0.5 / attempted retrieval requests.
- Latency: mean and nearest-rank P95 primary latency.
- Usage/cost: averages over rows marked usage-complete.
- Fallback rate: fallback agentic cases / eligible agentic cases.
- Paired differences: case-level `agentic - baseline` for comparable completed pairs only.

Learning metrics count events and distinct actor-task pairs, completed/submitted pairs, numeric
scores, total/average attempts, and feedback views over released workflows. The funnel requires a
chronological view → draft → submission → feedback → completion sequence. Inactivity is no activity
for 14 days and includes roster learners who have never been active. Inactivity uses each roster
learner's latest activity before the selected half-open range end, including activity before the
range start; historical reports use the range end rather than the current wall-clock time as their
as-of boundary. Detailed inactive learners are returned only through the page-size-100 endpoint,
whose envelope includes the applied filters, learner unit, numerator, denominator, sample size,
generation time, and excluded/incomplete count.

## Missingness and reproducibility

Measurement schema and policy versions are stored with every case. Missing scores, incomplete
usage, non-terminal rows, legacy measurements, model mismatch, technical judge results, and
unpaired cases are reported as exclusions rather than silently interpreted as zero. Legacy rows
are `legacy-v1` and non-comparable. Export serializers use stable v1 field order/encoding, and
automated golden tests protect reproducibility.
