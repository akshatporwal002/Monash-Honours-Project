# Task 32 study data plan

Status: `DRAFT_FOR_REVIEW`. Task 32 remains `PARTIAL`, with external approval gates open.

Draft version: `task-32-data-plan-draft-v3`. Prepared: 2026-09-07.

Research lead: Arv Surana. Role name supplied by the requesting user and recorded on 2026-09-07.
This names the research lead only. It does not approve the data plan, ethics, preregistration, retention, hosting, or operational authority.
Other role holders and all approval records remain pending.

This plan supports the [draft study protocol](task-32-study-protocol.md).
It proposes an exact field inventory for review and future Task 33 implementation.
No field is approved for live study use merely because it appears here.
No data collection, export, retention period, or deletion action is activated by this document.

## 1. Decisions and purpose boundaries

[Task 8](task-08-approved-selections.md) approves D-03 research grants, D-07 gated AI suggestions, and D-08 minimal study data.
It leaves named staff, studies, courses, fields, consent, retention, and withdrawal records open.
The [requirements](../01-implementation-requirements.md) govern BP13 purpose separation, BP14 lifecycle rules, and NFR25 export support.

Use distinct access layers for identity mapping, operational learning, formal assessment, preferences and access settings, and research.
Pseudonymous data remains re-identifiable. Do not label it anonymous.
Research consent controls research use. It must never grant or remove course access.
Teaching access, assessor status, and administrator status must not imply research permission.
Research condition must not change operational teaching access, adaptation, or formal results under Task 33.
Keep model snapshots and adaptations from separate study activities in research scope.
Do not write those study inferences or condition flags back into the operational teaching path.

Monash advises planning ethics and privacy together because consent and data handling affect later use and disclosure.
The research lead must obtain the relevant privacy review alongside the ethics decision. [Monash ethics and privacy guidance](https://www.monash.edu/research/infrastructure/research-data/working-with-your-research-data/ethics-and-privacy-responsibilities)
This plan does not determine applicable law or approve a hosting region.

| Layer | Proposed contents | Allowed purpose and access |
| --- | --- | --- |
| Identity and contact vault | Study-specific identity mapping and contact details needed for consent or approved follow-up | Named consent custodian; re-identification only for approved contact, withdrawal, or correction |
| Governance vault | Signed consent, study approval, grants, withdrawals, retention records, and export audit | Named research administrator and authorised governance reviewers |
| Operational learning | Existing course events, attempts, drafts, feedback, circuits, and activity history | Existing course access rules; no automatic research replication |
| Formal assessment | Frozen criteria, evidence, human decisions, reviews, and protected result history | Authorised learner and course assessor paths |
| Preferences and access | Interface settings and approved support details | Relevant learner, support, and teaching access; no diagnosis export |
| Restricted rating store | Minimised research probe responses and blinded reviewer packets | Named reviewers with approved study and evidence fields |
| Research analysis store | Study pseudonyms, permitted derived outcomes, and minimised sequence data | Named researchers with explicit study, course, field, and time grants |
| Approved outputs | Reviewed aggregate tables or scoped pseudonymous snapshots | Approved recipients and purpose only; no public participant-level release by default |

Use random study-specific pseudonyms. Do not derive them from student numbers, emails, or public hashes of identities.
Use separate pseudonyms across studies unless a new linkage purpose receives approval and consent.
Store the mapping separately from research data, with separate access controls and managed encryption keys.
Research analysts must not receive the mapping or direct institutional user IDs.

## 2. Governance inventory, excluded from analysis exports

The following proposed fields form an allow-list. Unlisted fields are denied pending a reviewed amendment.
Opaque references must resolve only within their authorised layer.
They must not expose storage paths, identity-bearing URLs, credentials, or direct operational user IDs.
All datetimes below use UTC ISO-8601. Version fields identify frozen records, not mutable labels.

| Record | Exact proposed fields | Purpose and access |
| --- | --- | --- |
| Study approval | `study_id`, `protocol_version`, `data_plan_version`, `approval_record_ref`, `approval_status`, `approved_course_ids`, `approved_field_set_version`, `valid_from`, `expires_at`, `suspended_at`, `closed_at`, `responsible_owner_ref` | Prove approved scope and validity; governance access only |
| Research grant | `grant_id`, `researcher_account_ref`, `study_id`, `course_id`, `field_set_version`, `allowed_field_paths`, `allowed_operations`, `valid_from`, `expires_at`, `revoked_at`, `grant_authority_ref`, `grant_decision_ref` | Enforce named researcher, course, study, fields, operation, and expiry under D-03 |
| Identity mapping | `study_id`, `participant_id`, `institution_user_ref`, `contact_route_ref`, `mapping_created_at`, `mapping_retention_rule_ref` | Link consent, contact, and withdrawal; identity custodian only |
| Consent evidence | `consent_record_id`, `study_id`, `participant_id`, `consent_version`, `information_sheet_version`, `consent_scope_codes`, `decision`, `decided_at`, `evidence_ref`, `withdrawal_rule_version` | Record explicit consent and its purpose; signed evidence stays in the governance vault |
| Eligibility | `study_id`, `participant_id`, `course_id`, `eligibility_rule_version`, `eligible`, `reason_code`, `checked_at` | Store the decision and bounded reason; do not copy identity documents or dates of birth |
| Allocation key | `study_id`, `participant_id`, `assigned_condition`, `stratum_code`, `form_sequence_id`, `allocated_at`, `allocation_record_ref` | Custodian-controlled allocation and later analysis join; withheld from outcome reviewers |
| Withdrawal | `withdrawal_id`, `study_id`, `participant_id`, `requested_at`, `effective_at`, `scope_code`, `withdrawal_rule_version`, `action_status`, `processed_at`, `decision_ref` | Block further use and document handling of prior data; no mandatory personal explanation |
| Export audit | `export_id`, `study_id`, `requester_ref`, `grant_id`, `field_set_version`, `filter_manifest_ref`, `consent_snapshot_ref`, `withdrawal_check_at`, `recipient_ref`, `purpose_code`, `created_at`, `expires_at`, `status`, `row_count`, `excluded_counts`, `artifact_hash`, `failure_code` | Reconstruct permission and delivery without copying participant answers into audit logs |
| Retention and disposal | `record_class`, `authority_ref`, `authority_version`, `trigger_event`, `minimum_rule`, `maximum_rule`, `review_due_rule`, `hold_status`, `owner_ref`, `approval_ref`, `disposal_method`, `disposal_evidence_ref` | Bind records to the approved class, holds, review, and authorised action |

`allowed_operations` must distinguish collection, rating, analysis, export, linkage, and disposal.
A study export grant does not grant identity linkage or disposal authority.
The grant expiry cannot extend beyond the approved study access period.
An expired or suspended study blocks use even when a researcher's course grant remains active.
The same check applies at collection, background processing, rating access, and export.

Consent scopes must name the main study, optional delayed contact, and any separately proposed future reuse.
Future reuse defaults to absent. Do not bundle it with course access or core study participation.
A declined invitation must not create a research pseudonym or response record.
Retain a minimal consent administration record only if the approved process permits it.
Aggregate recruitment counts need separate approval and must not expose who declined.

## 3. Restricted research evidence inventory

Probe evidence is needed for independent human rating. Keep it out of routine analysis exports.
Raw response handling is a proposed new restricted path, not permission to widen the existing v1 export.
The current [export schema](../../src-main/docs/research-export-schema.md) excludes raw student answers and drafts.
Task 33 must preserve that boundary while implementing any separately approved rating access.

| Record | Exact proposed fields | Minimisation and justification |
| --- | --- | --- |
| Probe evidence | `probe_id`, `study_id`, `participant_id`, `stage`, `form_id`, `form_version`, `item_id`, `item_version`, `response_mode_code`, `response_text`, `circuit_spec`, `submitted_elapsed_ms`, `capture_status`, `missing_reason_code` | Keep only the submitted study response and supported circuit structure needed to judge the construct |
| Evidence redaction | `probe_id`, `redaction_status`, `redaction_rule_version`, `reviewer_packet_ref`, `redaction_reason_code` | Remove self-identifiers before reviewer access; quarantine uncertain content |
| Reviewer rating | `probe_id`, `criterion_id`, `criterion_version`, `reviewer_code`, `rating`, `evidence_ref`, `reason_code`, `rated_at`, `rating_version` | Preserve each independent criterion judgement and its basis |
| Adjudication | `probe_id`, `criterion_id`, `original_rating_refs`, `adjudicator_code`, `resolved_rating`, `reason_code`, `evidence_ref`, `resolved_at` | Preserve disagreements and the authorised resolution |
| Blinding event | `probe_id`, `reviewer_code`, `breach_code`, `detected_at`, `handling_decision_ref` | Track known condition or timepoint disclosure without retaining unnecessary narrative |

Permit text entry and an approved structured alternative. Audio, video, screenshots, and full browser recordings are excluded.
If an access need requires another evidence type, review its purpose and storage before collection.
Do not require medical diagnoses to request equivalent access support.
Tell participants to avoid names or personal details in research responses.
Use approved redaction review, not a claim that an automated filter guarantees de-identification.
Retain original evidence only in the authorised restricted layer under its approved record class.

Reviewers see a separate packet identifier, instrument evidence, and permitted criterion metadata.
The packet must omit `assigned_condition`, hint history, consent choices, and operational AI suggestions.
The reviewer service resolves packet identifiers internally. It must not expose the allocation key.

## 4. Proposed analysis and learning-sequence export inventory

The field set below is `task-32-research-sequence-draft-v2`.
It is a proposed logical contract, not an implemented API version or migration.
It covers the study outcomes and NFR25's learning-sequence categories using minimal references and derived values.
Field-level approval must specify exact paths, including nested members.
There is no wildcard grant and no arbitrary metadata object.

| Group | Exact proposed fields | Need and constraints |
| --- | --- | --- |
| Envelope | `schema_version`, `study_id`, `protocol_version`, `data_plan_version`, `field_set_version`, `export_id`, `generated_at`, `approved_filters`, `record_count`, `excluded_counts`, `manifest_hash` | Reproduce one authorised extract; filters contain approved course, stage, condition, and time bounds only |
| Sequence identity | `sequence_id`, `participant_id`, `course_ref`, `stage`, `assigned_condition`, `delivered_condition`, `task_ref`, `task_version`, `form_id`, `form_version` | Link approved stages within this study; use study-scoped course and task aliases |
| Exposure and timing | `session_index`, `elapsed_day`, `duration_ms`, `response_mode_code`, `support_manifest_version`, `prior_experience_band`, `intervening_learning_code`, `contamination_code` | Model timing, equivalence, and known exposure; use relative dates and coarse categories |
| Research outcomes | `probe_id`, `criterion_id`, `criterion_version`, `criterion_rating`, `all_required_met`, `concept_criteria_met_count`, `concept_criteria_total`, `rating_protocol_version`, `adjudication_ref` | Calculate learning endpoints; count only the approved instrument criteria |
| Evidence lineage | `evidence_refs`, `evidence_types`, `capture_status`, `missing_reason_code`, `comparability_status`, `exclusion_reason_code` | Trace judgements and explain missingness; references do not embed raw answers |
| Formal assessment context | `outcome_ref`, `bloom_target`, `assessment_version`, `pass_rule_version`, `formal_result`, `review_state`, `assessment_decision_ref` | Distinguish approved assessment context from the research endpoint; no legacy numeric grade |
| Learner model and adaptations | `learner_model_snapshot_ref`, `learner_model_version`, `adaptation_refs`, `adaptation_rule_version`, `adaptation_reason_codes`, `selected_activity_ref`, `activity_scope` | Inspect lineage without copying the full learner profile; distinguish `study_activity` from authorised read-only `course_observation` |
| Help and revisions | `conceptual_hint_count`, `approved_hint_refs`, `support_stage`, `revision_count` | Describe assistance without applying a count cap or result penalty |
| Overrides | `override_refs`, `override_reason_codes`, `overridden_decision_ref` | Preserve the route to a human decision; no staff identities or free-form reasons |
| Sources | `source_refs`, `source_versions`, `source_locator_refs` | Trace approved grounding; exclude source chunks and identity-bearing display labels |
| AI generation | `ai_output_ref`, `ai_output_status`, `provider_id`, `model_id`, `model_version`, `prompt_version`, `feedback_policy_version`, `evaluator_release_ref` | Identify the output and versions; exclude prompt text and unrestricted generated prose |
| Quality judge | `judge_result_ref`, `judge_policy_version`, `judge_decision`, `unsupported_claim_count`, `regeneration_count`, `fallback_used` | Audit feedback screening; these values do not establish learner attainment |
| Simulation | `simulation_ref`, `simulation_version`, `simulation_status`, `simulation_config_ref`, `simulation_evidence_ref` | Connect the exact circuit and settings to evidence; exclude executable code |
| Resources | `primary_latency_ms`, `input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost`, `cost_currency`, `cost_basis_version`, `usage_complete` | Report technical usage with units, currency, and completeness |
| Reproducibility | `measurement_schema_version`, `condition_manifest_version`, `analysis_version`, `row_status`, `field_missingness` | Distinguish legacy, partial, withdrawn, and non-comparable records |

Use these proposed `stage` values consistently across approved evidence records and sequence exports:

| Stage value | Protocol stage and evidence boundary |
| --- | --- |
| `T0_BASELINE` | Baseline research probes |
| `T1_STUDY_ACTIVITY` | Separate voluntary supported study activity |
| `T1_FORMAL_SUPPORTED` | T1a common formal assessment stage with unrestricted approved conceptual hints |
| `T1_FORMAL_UNAIDED` | T1b separate fresh unaided transfer within the same formal assessment, for both arms |
| `T2_CONCEPTUAL` | Additional immediate unaided conceptual research probe |
| `T2_TRANSFER` | Additional immediate unaided transfer research probe; never a substitute for T1b |
| `T3_CONCEPTUAL` | Optional approved delayed conceptual research probe |
| `T3_TRANSFER` | Optional approved delayed transfer research probe |

`support_stage` uses `supported` or `unaided` according to the corresponding protocol stage.
T1a and T1b share the approved formal assessment version while preserving their distinct stage and evidence references.
Formal stages use `course_observation`; the separate study activity and research probes use `study_activity`.
T1b records retain approved accessibility support without treating it as instructional assistance.
No stage value grants research access to formal records without the required consent and field approval.

`field_missingness` maps only approved field paths to approved reason codes.
Use `not_collected`, `not_applicable`, `participant_skipped`, `technical_failure`, `not_evaluable`, `outside_window`, `withdrawn`, or `not_approved`.
Use typed null values with a reason when an approved applicable field lacks data.
Required envelope and scope identifiers cannot be null; invalid scope excludes the record before export.
Omit fields outside the grant entirely. They must not become null placeholders that reveal unapproved categories.

Arrays contain bounded opaque references or controlled codes only.
Controlled categories and size limits must be frozen in the approved dictionary before Task 33 activation.
`prior_experience_band` uses `none`, `some`, or `not_reported`; exact course histories are excluded.
`intervening_learning_code` uses `none_reported`, `reported`, or `not_reported`; do not collect a diary or browsing history.
`response_mode_code` describes an approved interaction mode, not a diagnosis or disability label.

The field set is a maximum proposed study scope. Approvers should remove fields lacking a study-specific purpose.
If formal assessment or model lineage fields are unnecessary for the approved analysis, exclude them from that extract.
NFR25 still requires the application to support each approved sequence category under its own permissions.
Do not claim full NFR25 delivery when only references are exported and authorised evidence cannot be retrieved.
Task 33 must show how each approved reference resolves through a separately scoped access check.
Research consent does not grant source redistribution rights or provider permission to reuse student responses.

## 5. Excluded data and export behaviour

Do not collect names, emails, student numbers, dates of birth, precise location, IP addresses, or device fingerprints in research analysis.
Exclude diagnoses, disability documents, ethnicity, gender, financial data, and other sensitive demographic profiles from this proposed study.
Any later subgroup purpose requires an explicit instrument, consent, field, access, and disclosure amendment.
Do not copy preferences, raw drafts, keystrokes, conversation history, source passages, prompts, credentials, or raw exceptions into exports.
Do not export direct staff identifiers, unrestricted assessor comments, or operational storage paths.

The current [measurement schema](../../src-main/docs/research-schema.md) covers technical pairs, not this full learning-study contract.
The [restriction record](research-access-restriction.md) describes production research as blocked pending governed activation.
These drafts do not reopen the runtime handoff, baseline worker, or export route.
No backlog may be resumed by assuming that new study consent applies retrospectively.
The research lead must decide eligibility and purpose for each historical record class before any proposed reuse.

At each export, intersect the active grant, approved study, course scope, consent scope, field set, and permitted recipient.
Recheck withdrawal and expiry before releasing data. Define how revocation during streaming stops further release.
Make audit preparation durable before any response bytes, preserving the existing fail-closed export boundary.
Snapshot the eligibility decision for reproducibility without treating it as permanent permission.
Record excluded counts by reason. Do not put withdrawn participant rows into routine analysis exports as tombstones.

Keep CSV and JSON schemas versioned and deterministic.
Preserve spreadsheet formula protection, bounded nested data, sanitised failure codes, and stable encoding from the existing export contract.
Do not reuse the v1 schema identifier for a changed field set.
Use synthetic sentinels to verify that hidden fields cannot escape through identifiers, nested objects, logs, or filenames.

Pseudonymous participant-level extracts stay in the approved research environment by default.
Public reports contain reviewed aggregates only.
The privacy reviewer must approve minimum cell-size and complementary suppression rules before publication.
No numeric suppression threshold is approved here.
Until that rule exists, do not publish subgroup tables or participant-level artifacts.
Review free text, linked references, rare combinations, and figure labels as well as table cells.

## 6. Consent, withdrawal, and correction

Consent materials must explain randomisation, procedures, burden, provider use, fields, recipients, storage, retention, and withdrawal limits.
List research and course contacts separately. Name an independent complaint route in the approved materials.
Refusal leaves the normal course and assessment journey available.
Withdrawal must stop new research collection and optional follow-up without affecting teaching access or formal results.

Use the following proposed lifecycle, subject to the signed withdrawal rule.

1. Verify the request through the consent custodian without exposing identity to analysts.
2. Record its scope and effective time, then block new research processing and exports.
3. Locate approved research derivatives, reviewer packets, and delivered extracts through study pseudonyms and export audit.
4. Apply the approved rule for removal from ongoing analysis or restricted retention.
5. Notify authorised recipients through the approved process and track required handling of their copies.
6. Confirm the action and any limits to the participant through the custodian.

The exact cutoff for removing already aggregated or published data remains unresolved.
Consent materials must explain what can be withdrawn before and after that cutoff.
Do not promise removal from completed publications or irreversibly anonymous aggregates when that cannot be delivered.
Do not use this limitation to keep collecting after withdrawal.
The data owner must distinguish ending research use from deleting records that have a separate retention duty.

Preserve formal assessment history under its own access and retention rules.
Research withdrawal does not erase course results or permit rewriting an assessor's decision.
Corrections retain the original version, correction reason, authority, and affected derivative references.
Research outputs use the approved corrected version and disclose material changes.

## 7. Retention, storage, and disposal schedule

No blanket deletion period is approved or proposed.
Monash assigns researchers responsibility for deciding retention with legal, funder, publisher, ethics, and other requirements in view.
The data owner must document the applicable record class and trigger for this study. [Monash researcher responsibilities](https://www.monash.edu/research/infrastructure/research-data/researcher-roles-and-responsibilities)

Monash's archive guidance links minimum retention to project requirements and its Retention and Disposal Authority.
It also describes review with the data owner at the retention period's end. [Monash MURDA guidance](https://docs.erc.monash.edu/Storage/StorageProducts/MURDA/)
This draft does not claim that every record belongs in MURDA or has the same retention period.

| Record class to resolve | Owner roles and known holder | Required schedule decision |
| --- | --- | --- |
| Identity mapping and follow-up contact | Consent custodian and privacy adviser | Applicable class, final contact/withdrawal trigger, linkage need, minimum and maximum rules |
| Consent, approval, and withdrawal evidence | Responsible investigator and records adviser | Applicable class, closure trigger, proof obligations, and restricted access after withdrawal |
| Raw probe responses and rating packets | Research data owner | Primary evidence class, publication or closure trigger, reviewer copy expiry, and allowed redaction |
| Derived outcomes and analysis scripts | Arv Surana, research lead; records adviser pending | Research evidence class, reproducibility requirements, version retention, and review date |
| Operational learning records | Course data owner | Teaching record class, course trigger, student correction rules, and independent research-use limits |
| Formal assessment and review history | Assessment records owner | Assessment record class, appeals or other holds, preserved versions, and separate disposal authority |
| Preferences and support settings | Product data owner and privacy adviser | Access-purpose class, change or account closure trigger, and minimum necessary history |
| Grant and export audit | Security and research data owners | Accountability class, access-period trigger, incident holds, and recipient-copy tracking |
| Backups, replicas, and caches | Operations owner and data owner | Approved backup window, expiry propagation, restore restrictions, and verification evidence |

Every schedule entry needs an authority reference and version, trigger, retention rules, review date, named owner, and approval record.
Record any legal, complaint, appeal, incident, or research-integrity hold before considering disposal.
Missing schedules block live collection and destructive handling. They do not justify indefinite unreviewed storage.
Assign a review owner for existing held records while governance resolves the schedule.

Before activation, record approved hosting, location, encryption, backups, access logging, recipient agreements, and provider processing terms.
Operations must verify key separation, least-privilege accounts, revocation, and recovery in the selected environment.
Do not place human study records in this repository, shared scratch folders, local test fixtures, or agent transcripts.
Do not send probe responses to external AI providers merely because the learning platform has provider credentials.
Any required provider processing needs specific institutional approval and clear participant information.

Disposal needs the approved schedule, hold check, named authority, exact scoped inventory, and verified method.
Retain a minimal disposal audit without retaining the disposed content.
Research access expiry closes access; it is not automatic permission to delete.
Backups must not restore withdrawn records into active research use.
Restore into a restricted state, replay withdrawal and revocation records, validate eligibility, then authorise normal access.
Task 33 and the operations owner must test this sequence with synthetic records before activation.

## 8. Task 33 interface and release evidence

The implementation must enforce the approved plan; the plan alone does not enforce it.
Task 33 owns the policy records, permission checks, data contracts, withdrawal handling, and scoped export path.
Arv Surana, the research lead, owns purpose, study conditions, consent, and field justification.
Privacy and records advisers own their required review decisions alongside the named institutional data owner.
Operations owns storage, access, backups, incident handling, and expiry evidence.

Required checks include denied collection without consent; wrong-study and wrong-field grants; expiry; revocation; and suspended study access.
Check exports against exact approved paths, including nested fields and reference resolution.
Check refusal and withdrawal preserve course access and assessor-confirmed results.
Check study allocation and study model changes cannot alter operational teaching adaptation or assessment rules.
Check withdrawal during queued work, export preparation, delivery, and restore.
Check legacy records remain excluded unless a separate historical-use decision permits them.
Check logs, errors, filenames, CSV formulas, reviewer packets, and aggregate disclosure controls.
These are future implementation acceptance checks, not tests claimed as passed by this document.

| Pending record | Required owner and evidence | Blocking effect |
| --- | --- | --- |
| `T32-DATA-FIELDS` | Arv Surana, research lead, and a privacy reviewer must sign exact field paths, purposes, modes, and recipients. Privacy reviewer pending. | No participant collection or export |
| `T32-CONSENT` | Responsible investigator supplies approved participant materials, consent version, and withdrawal rule | No recruitment or enrolment |
| `T32-RETENTION` | Named data owner and records adviser resolve every schedule class and hold process | No live collection or destructive disposal |
| `T32-ACCESS` | Grant authority names researchers, courses, studies, fields, operations, and expiry | No research access |
| `T32-STORAGE` | Operations and institutional approvers record hosting, provider, security, backup, and incident arrangements | No live study processing |
| `T32-DISCLOSURE` | Privacy reviewer approves recipient rules, suppression, and final output review | No study disclosure |
| `T33-ENFORCEMENT` | Research backend and privacy owners provide reviewed implementation evidence for the approved versions | No production research activation |

Arv Surana is the named research lead. Other named holders and all approval identifiers remain pending.
Each signed record must link the protocol and data-plan versions it approves.
The research lead must include the approved versions in preregistration before recruitment, as required by BP12.
Task 32 remains `PARTIAL`; Task 33 remains a separate implementation and verification gate.

<!-- Manual completion requested by the user on 2026-09-09. Each entry needs a real named owner, date, scope, version and evidence reference. -->
<!-- TODO T32-DATA-FIELDS: Arv Surana and the named privacy reviewer must approve exact field paths, purposes, collection modes and recipients. -->
<!-- TODO T32-CONSENT: Attach approved participant information, consent version, withdrawal process/cutoff and independent complaint contact from the responsible investigator. -->
<!-- TODO T32-RETENTION: Name the data owner and records adviser; complete every record class, authority/version, retention trigger, review date and hold process. -->
<!-- TODO T32-ACCESS: Name grant authority/researchers, approved courses/studies/fields, operations access and expiry dates. -->
<!-- TODO T32-STORAGE: Attach institutional host/provider approval, location, encryption, backup/restore, access logging and incident owner arrangements. -->
<!-- TODO T32-DISCLOSURE: Name the privacy reviewer; approve recipient controls, small-cell/complementary suppression and final output review. -->
<!-- TODO T33-ENFORCEMENT: Link tested consent, revocation, withdrawal, field filtering and restore enforcement for these exact approved versions before activation. -->
