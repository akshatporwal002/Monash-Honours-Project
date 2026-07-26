# Research export schema

Research exports are authorization-scoped, terminal-only snapshots. They are fail-closed on the
initial `research_export_created` audit write: no response bytes may be sent until that record is
durable. A stream failure creates a sanitized failed audit event.

## Filters and limits

The export route supports CSV or JSON plus course, UTC half-open date range, condition, task type,
model, and judge-decision filters. The date range is at most 365 days. Course scope is intersected
with authorization and is bounded to 1,000 course references per synchronous request. Results are
streamed in batches of 1,000 and the synchronous export cap is 100,000 rows.

## Stable v1 fields

CSV uses this fixed order:

```text
case_id,pseudonymous_user_id,course_id,task_id,task_type,submission_reference,
experimental_condition,input_reference,retrieved_sources,simulation_reference,
generated_output,judge_decision,judge_reason,correctness_score,relevance_score,
grounding_score,actionability_score,safety_score,unsupported_claim_count,latency_ms,
input_tokens,output_tokens,total_tokens,estimated_cost,regeneration_count,fallback_used,
status,failure_category,comparable,usage_complete,measurement_schema_version,created_at,
completed_at
```

Nested values use canonical sorted JSON. Timestamps are UTC ISO-8601. Costs are fixed decimal
strings. Every CSV field is quoted, UTF-8 output has a BOM, and cells beginning with `=`, `+`, `-`,
or `@` after optional whitespace, plus tab/newline/control-prefixed cells, are prefixed with an
apostrophe to prevent spreadsheet formulas.

JSON uses a `quantumlearn.research-export.v1` envelope with `generated_at`, applied filters,
`record_count`, and records. Filenames contain only the fixed `quantumlearn-research-` prefix and
a UTC timestamp.

Exports contain pseudonyms only and exclude raw answers/drafts, prompt text, source chunks, direct
identities, credentials, report/feedback prose copied from student surfaces, and raw exceptions.
Input references are bounded opaque strings. Retrieved sources are strictly limited to bounded
`source_id`, display `label`, and finite 0-1 `relevance_score` values. Structured generated output
is bounded by encoded bytes, nesting depth, node count, collection size, and string size, and is
recursively rejected when sensitive key variants or credential-like values are present.

Legacy or corrupted terminal rows that fail this privacy contract are excluded fail-closed.
Failed rows must carry only a bounded lowercase sanitized failure category, while non-failed rows
must not carry one.
Counting and streaming apply the same validation, so the JSON `record_count` cannot advertise a
row that is omitted from the stream. Iterator failures, task cancellation, and client-closed
streams append the same sanitized failed-export audit event before preserving control flow.
