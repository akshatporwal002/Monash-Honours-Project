# Evaluator validation and signed suggestion release

This delivery supplies the D-07 administrator workflow and retained-output assessor seam. It does not appoint experts, certify external documents, approve a real evaluator, call a provider or confirm a learner result. No real release has been recorded by this development work.

## Administrator workflow

Open **Evaluator validation for [course]** in the administrator workspace. The panel shows the current dependency fingerprint, approved task forms and preserved validation, release, invalidation and revocation records. Expand **Evidence references** to inspect named experts, their appointment/training references, error limits, coverage, signed authority and expiry.

1. Collect real independent expert ratings and adjudications using the existing Task 35 bundle contract. The validation runner checks immutable manifests, exact outputs and rating provenance. Draft or synthetic fixtures are not expert evidence.
2. Supply the signed approval record described below and prepare an import packet. The packet must identify the current course fingerprint and a future validation expiry.
3. Upload the packet under **Record completed validation**. Recording evidence leaves suggestions `PENDING`.
4. After a separate authorized release decision, enter its authority name/role, reference, approval/expiry times, provider/model/prompt/retrieval versions and exact approved task forms. The release must follow the current validation and expire no later than that validation. Provider and model must match the validated configuration.
5. Use **Revoke validation or release** with a reason and authority reference to withdraw permission. Reload history after conflicts or permission changes. Earlier records remain available to authorized administrators.

The actor recording each decision is the authenticated active administrator. A typed authority name or external reference is a retained attestation; the application cannot authenticate the external signature or establish that someone has actually been appointed.

## Preparing a validation packet

From `src-main/backend`, with the supported backend environment:

```powershell
python -m scripts.task35_validation.release_packet --approval-schema
python -m scripts.task35_validation.release_packet --bundle actual-bundle.json --current-manifest current-manifest.json --approval-record signed-approval-record.json --expected-fingerprint <current-course-fingerprint> --expires-at 2026-12-01T00:00:00Z --output validation-packet.json
```

`--approval-schema` prints the exact JSON input contract without creating a decision. An approval record contains these references: `release_approval`, `expert_review`, `approved_cases`, `human_agreement`, `fairness_review`, `revalidation_policy`, `threshold_approval`; approved numerical `max_false_pass` and `max_false_incomplete`; and `assessment_gate` plus `baseline_key`.

The assessment gate requires at least two distinct named experts with appointment, expertise and training records; approved population/statistic and uncertainty references; task-type, alternate-form, concise-style, unusual-method and relevant-group coverage; adjudication and review-trigger records; and explicit sample and baseline minima. No proposed kappa, sample or error threshold is installed as an approved default. `baseline_key` names an entry in the runner's `human_baseline`; `baseline_statistic` is `agreement` or `cohen_kappa`, and `baseline_value` must match that reported value. Undefined statistics cannot satisfy this preparation tool.

The tool runs the existing validator, requires current recorded evidence and its quality targets, rejects omitted or unresolved assessment cases, checks the approved case count and assessment reviewer identities, derives the two error rates from their own denominators and enforces the supplied maxima. It retains bundle, manifest and report digests, selected baseline, error denominators and uncertainty information. It neither invents missing records nor overwrites an existing packet. The administrator must ensure the recorded validation actually covers the current course snapshot, selected forms and population; a copied fingerprint is not proof that external experiments were performed.

The existing validation endpoint remains compatible with older evidence records. Those records cannot release suggestions without the complete assessment gate and a separate signed release. Validating again supersedes an earlier release and returns suggestions to `PENDING`.

## Assessor output records

From an unresolved assessment, open **AI suggestion records**. Actual retained outputs can be imported only for the current signed release and exact task form. Imports bind the frozen response digest, all frozen criteria, approved evidence references and provider/model/prompt/retrieval versions. Generated time must follow both the learner response and release approval.

Each import is an append-only evidence artifact, separate from criterion decisions and formal assessment results. Assessors inspect suggestions and independently enter their own decisions; the panel does not populate decisions or calculate a formal result. Independent second-review access withholds suggestions, and the moderation UI does not request them.

Before an output joins the suggestion list, choose **Prepare output quality review**. Inspect the candidate and its frozen evidence, then explicitly record a finding, reason and supporting evidence for each of FR17's ten dimensions. There are no preselected findings. This is a review of the candidate's quality, not a learner assessment. The server binds the human reviewer to the authenticated assessor and checks the exact candidate, response, standards, evidence and release versions. Missing, stale, unverified or violated reviews produce retained `REJECTED` quality records. Only a complete `APPROVED` quality record permits suggestion display. Neither quality approval nor model release confirms a learner result.

The corresponding API is `POST /assessment/attempts/{attempt_id}/ai-suggestions/quality-context`, followed by `POST /assessment/attempts/{attempt_id}/ai-suggestions` with the returned request digest, authenticated reviewer metadata and explicit findings in `quality_review`. The import contract is `SuggestionImportWrite`; its fields include a stable idempotency key, release ID, expected fingerprint, frozen response digest, provider/model/prompt/retrieval versions, output reference, aware generation time and exactly one decision/reason/evidence list per frozen criterion. A rejected import is preserved for audit and does not appear in `GET /assessment/attempts/{attempt_id}/ai-suggestions`.

Every read/import rechecks release authority and dependencies. Expiry, revocation, material dependency changes or live moderation drift close access to released suggestions while preserving history. The open panel hides records when the displayed release expires; use **Reload suggestion records** to refresh other governance changes. It does not provide continuous remote revocation push notifications.

## Boundaries and remaining activation records

- BP9 original, second, resolution and drift moderation, approved sampling settings and human confirmation remain in the existing moderation workflow.
- BP10 evidence records now have usable validation and release controls; actual approved expert evidence, coverage, numerical limits, uncertainty interpretation and signed authority remain required.
- BP11 invalidation is enforced against the current dependency fingerprint, with historical artifacts and results preserved.
- Task 28 already has separate queues, named primary/backup configuration, explicit case deadlines, audited state transitions, notices and manual accepted-feedback sampling. Its targets are free text and deadlines are entered explicitly against the operator's approved staffing calendar and timezone. D-09 requires confirmed staffing before service promises; it does not require an automatic business-time scheduler. Record the real staffing, calendar/timezone, severity, resolution and sampling approvals in queue configuration references before making those promises.
- Research study activation is a separate workflow and release decision. No research flags or approvals are changed here.

No shared Task 35 manifests, generated validation artifacts or requirements ledgers are regenerated by this delivery.

## Focused verification

Synthetic fixtures exercise the tooling and do not constitute evaluator approval:

- `test_evaluator_release_workflow.py`: 19 checks, including migrated immutable history, API authority, exact scope, expiry, revocation, blinding and missing/unverified/spoofed/stale quality rejection.
- `test_evaluator_release_packet.py`: 8 preparation checks, including draft rejection, actual-rate derivation, denominator, baseline, sample and reviewer-record failures.
- Three existing live-moderation checks cover stable validation, durable expiry and route permissions.
- `EvaluatorGovernancePanel.test.tsx`: 7 UI checks cover separate signed release, course isolation, withdrawn permissions, independent moderation, revocation, fingerprint mismatch and explicit ten-dimension quality review. The existing 11 human-assessment UI checks also pass.
- Scoped Ruff, ESLint and frontend application type checks pass. The packet command's help entry point runs with the supported Python environment. Full suites and dependency installation were not run.
