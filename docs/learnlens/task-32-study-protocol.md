# Task 32 learning-study protocol

Status: `DRAFT_FOR_REVIEW`. Task 32 remains `PARTIAL`, with external approval gates open.

Draft version: `task-32-protocol-draft-v3`. Prepared: 2026-09-07.

Research lead: Arv Surana. Role name supplied by the requesting user and recorded on 2026-09-07.
This names the research lead only. It does not approve the protocol, ethics, preregistration, retention, hosting, or operational authority.
Other role holders and all approval records remain pending.

This document makes the proposed study reviewable. It does not approve recruitment, participant data collection, or research activation.
No participant results, ethics decision, power calculation, or preregistration record have been supplied.
Every study design detail below is proposed unless tied to an approved Task 8 selection.

## 1. Scope and controlling records

The study asks whether supported LearnLens activity improves learning that students can demonstrate without instructional help.
It focuses on introductory single-qubit Hadamard circuits at Bloom APPLY.
The [Task 32 acceptance criteria](../../LearnLens_Remaining_Tasks.md) require an approved learning protocol and data plan.
The [data plan](task-32-data-plan.md) defines the proposed field inventory and access boundaries.

The full [Task 8 approved selections](task-08-approved-selections.md) control earlier conflicting proposals.
Selected directions are settled. Their missing course, staff, instrument, and study records remain open.

| Selection | Boundary preserved by this draft |
| --- | --- |
| D-03 A | Named researchers need grants for approved courses, studies, fields, and access periods. Consent remains a separate check. |
| D-04 A | Use one multipart Hadamard assessment at APPLY. Prediction, explanation, and fresh application must all meet their criteria. |
| D-05 B | Allow unrestricted approved conceptual hints during the supported assessed stage. Use separate unaided transfer to judge independent application. |
| D-07 C | AI suggestions may reach assessors only after a separate validation gate passes. Humans confirm formal results. |
| D-08 A | Minimise study fields, use separate pseudonyms and identity mapping, and separate consent from course access. Use approved retention classes. |

The [implementation requirements](../01-implementation-requirements.md) supply BP12, BP13, BP14, and NFR25.
The [architecture](../../LearnLens_Architecture_and_Sources.md) requires unaided learning evidence before claims of learning improvement.
This draft relies on that local design boundary. It does not independently validate the architecture's cited papers.

The [current methodology](../../src-main/docs/research-methodology.md) compares paired feedback workflows.
Its `agentic_rag` and `single_step_baseline` records share a workflow, rather than randomly assigned students.
The baseline runs after student feedback is saved and does not become a student learning condition.
Judge quality, latency, tokens, costs, and paired output differences therefore remain technical outcomes.
The current documentation also describes legacy numeric learning metrics. These must not define the new formal assessment outcome.

## 2. Research question and hypotheses

No existing verbatim research question was found in the supplied acceptance criteria, methodology, architecture, or tracked Markdown.
The research lead must supply the authoritative wording and source, or approve the proposed question below.
If another source defines the question, copy it verbatim into the signed protocol before preregistration.
Do not present this proposed wording as an already approved research question.

Proposed operational question:

> For students learning introductory single-qubit Hadamard circuits, does LearnLens support improve unaided conceptual understanding and fresh transfer compared with a matched course-material learning condition?

The proposed main hypothesis concerns fresh transfer immediately after the learning activity.
Students assigned to LearnLens will more often meet all transfer criteria than students assigned to the comparator.
The main null hypothesis is no difference in that probability between assigned conditions.
Use a two-sided analysis, even though the expected direction favours LearnLens.

Unaided conceptual understanding is a secondary outcome.
Delayed retention is a proposed secondary extension with a separate follow-up session.
Neither outcome may replace the primary outcome after results are known.
The research lead and methods reviewer must approve the exact question, estimand, instruments, and analysis record.

## 3. Design and comparison conditions

Use a proposed two-arm, parallel, individually randomised feasibility study with exploratory learning estimates.
The participant is the allocation and primary analysis unit.
Repeated responses, attempts, and feedback outputs do not increase the participant sample size.
Do not claim a powered efficacy trial until a reviewed sample-size calculation supports that claim.

| Feature | LearnLens condition | Matched comparator |
| --- | --- | --- |
| Learning content | Approved introductory Hadamard sources and task forms | Same approved sources, concepts, and equivalent forms |
| Learning workspace | LearnLens circuit, prediction, explanation, simulation, and feedback flow | Same circuit and simulation workspace with educator-written guidance |
| Conceptual help | Unrestricted approved conceptual hints from the supported workflow | Unrestricted access to an approved static conceptual hint bank |
| Personalisation within the separate study activity | Approved evidence-based adaptation and grounded tutoring, if released | Fixed activity order and static guidance |
| Assessment | Same approved criteria, human confirmation, and support policy | Same approved criteria, human confirmation, and support policy |
| Research probes | Separate unaided conceptual and fresh-transfer forms | Equivalent probes under the same conditions |

The contrast estimates the effect of the delivered support package.
It does not isolate each agent, retrieval step, simulation feature, or learner-model component.
The comparator must be built and checked before recruitment. Its existence is not established by this draft.
The shadow `single_step_baseline` must not be exposed as the comparator through an export or worker setting.

Freeze the delivered components, prompts, sources, task forms, model configuration, and teaching rules in a condition manifest.
Record unavailable features instead of labelling an incomplete condition as the full architecture.
Use the same planned learning session duration, teaching contact, devices where feasible, and approved access supports.
Record actual duration and faults. Equivalent access needs can change duration without lowering assessment standards.
Exact session length and permitted tools require instrument and course approval.

Both conditions retain ordinary course access, materials, assessment review, and essential support.
Participation or withdrawal must not affect formal results or course standing.
Task 33 also requires research condition to leave operational teaching access, adaptation, and formal results unchanged.
The proposed contrast therefore belongs in separate, voluntary study activities outside the operational course adaptation path.
It must not switch a learner's live teaching policy or write research-derived updates into the operational learner model.
Both arms retain the same ordinary teaching adaptation and formal assessment rules.
Study activity records and model snapshots remain research-scoped, with no automatic promotion into teaching records.
The course lead must approve that separation before the comparator can be used.
If the design requires changing operational teaching by assigned condition, this proposal cannot proceed under Task 33.
Record that conflict for an explicit requirements decision rather than treating ethics approval as permission to override it.
The research lead and course lead must approve any later access to the other condition.
Any planned crossover occurs after the final approved research probe to protect the comparison.

## 4. Eligibility, recruitment, and allocation

Proposed eligibility is an adult learner in the named approved introductory course or equivalent approved learner group.
The study must name its age boundary, course, prerequisite knowledge, recruitment period, and capacity checks before recruitment.
No course or participant group is approved here.
Prior quantum experience is recorded as a minimal coarse category and baseline performance, not grounds for retrospective removal.
Any prior-experience exclusion must be justified and frozen before recruitment.
Do not exclude learners because they need approved accessibility support, work slowly, or request many hints.

Recruitment materials must state voluntary participation, procedures, burden, data use, withdrawal limits, and contacts.
A consent coordinator outside the learner's marking relationship should manage enrolment where practical.
Assessors should not see consent choices unless needed for a separately authorised duty.
No incentive or participation credit is proposed here. Any later incentive needs approved terms and a non-coercion review.

Complete consent and baseline measures before revealing allocation.
Propose 1:1 allocation using a reproducible computer-generated sequence with variable block sizes.
An independent allocation custodian holds the seed, sequence, and block sizes.
Recruiting staff must not see upcoming assignments.
Stratify by course only if multiple courses are approved and each supports feasible allocation.
Freeze the exact blocks and strata in a restricted allocation record before recruitment.
Publish the method in preregistration without exposing future assignments.

Students may share guidance outside sessions. Record known contamination using a short neutral question, without collecting message content.
Keep contaminated participants in the assigned-condition analysis where consent permits.
A predeclared sensitivity analysis may exclude major condition crossover.
If classes must be allocated together, stop and amend the design before recruitment.
Cluster allocation needs a new sample-size basis, analysis, and approval. It is not a routine substitution.

## 5. Sequence, instruments, and support

The proposed instruments form one versioned set with approved equivalent forms and criterion anchors.
Expert review must check content coverage, ambiguity, accessibility, difficulty, and answer leakage before study use.
No validated instrument or human pilot evidence is claimed here.
Human instrument piloting also requires the relevant ethics decision and consent.

| Stage | Proposed instrument and purpose | Help conditions |
| --- | --- | --- |
| T0 baseline | Unaided conceptual items and a fresh application probe establish initial understanding. Use unrevealed forms. | Approved accessibility support only; no tutoring, source lookup, or simulation-generated answers. |
| T1 separate study activity | Voluntary study activities deliver the assigned support outside the operational teaching path. | Unrestricted approved conceptual hints. No worked answers. Preserve approved access supports. |
| T1a common formal supported stage | Both arms complete the supported prediction and explanation components of one multipart Hadamard assessment at APPLY. | Unrestricted approved conceptual hints, with no hint-count penalty. No worked answers. Preserve approved access supports. |
| T1b common formal unaided transfer stage | Both arms complete a fresh application component within that same multipart assessment. This separate stage supplies formal evidence of independent application. | No instructional hints, worked answers, external tutoring, or answer-producing tools. Preserve approved accessibility support and the approved restricted tool list. |
| T2 immediate conceptual probe | An equivalent unseen form tests the relationship between circuit operations, probabilities, and explanations. | Unaided under the approved tool list. Record access support without a result penalty. |
| T2 immediate transfer probe | A distinct unseen Hadamard application tests prediction, explanation, and application in a changed task context. | Separate unaided stage. No instructional hints, answer reveal, or external tutoring. |
| T3 delayed extension | Fresh equivalent conceptual and transfer forms assess retention after a proposed 14-day interval, with a proposed window of days 12 to 16. | Same unaided rules and equivalent access support. Record intervening learning and the actual interval. |

The proposed delayed interval and window require approval. They are not an existing course rule.
If T3 is omitted before preregistration, remove retention hypotheses and claims from the approved study.
Do not infer retention from platform activity, repeat submissions, or elapsed time alone.
Report follow-up outside the window separately under the frozen analysis rule.

T1a and T1b are separate stages within the same multipart formal assessment in both arms.
Prediction, explanation, and fresh application must all meet their criteria within that assessment under D-04.
D-05 requires T1b unaided transfer in addition to T1a supported work.
Freeze the formal stage boundary, permitted tools, fresh form, and equivalent access conditions before use.
Do not reveal the T1b task or answers during T1a, or carry instructional help into T1b.
T2 is a further distinct research probe. It does not silently add a new formal pass requirement.
T2 cannot substitute for the required T1b formal unaided transfer stage.
Study activities do not replace that common assessment or change its policy by assigned research condition.
Research outcomes cannot replace, average, or downgrade an assessor-confirmed course result.
Formal reassessment remains governed by D-06, with preserved history and fresh equivalent tasks.
Research measurement uses the first scheduled valid probe, subject to the technical replacement rule below.

Prepare separate item pools for baseline, supported work, formal unaided transfer, immediate probes, delayed probes, and approved technical replacements.
Counterbalance equivalent form sets across conditions using the allocation record.
Never reuse revealed answers as fresh-transfer evidence.
The assessor must approve what changes between forms and why the construct remains equivalent.
A changed label alone does not establish transfer.

Unaided means no instructional assistance or answer-producing tools during T1b formal transfer or the research probes.
Approved screen readers, alternative input, breaks, and equivalent access adjustments remain available.
The approved support manifest must distinguish access support from help that supplies the target reasoning.
Do not collect diagnoses to describe the support received.
Any construct-changing support requires assessor review and an explicit comparability decision.

## 6. Outcomes and rating rules

The proposed primary outcome is immediate fresh-transfer success at T2 for each participant.
Success requires all approved prediction, explanation, and application criteria to be met on that probe.
Store item and criterion judgements as `MET`, `NOT_MET`, or `NOT_EVALUABLE` with evidence references.
The research endpoint is `MET_ALL` or `NOT_MET_ALL` only when all mandatory criteria are evaluable.
Use a missing outcome with a reason when required evidence cannot be evaluated.
This research endpoint is distinct from formal `PASS` or `INCOMPLETE` and assessment review state.

| Outcome | Definition and reporting boundary |
| --- | --- |
| Primary transfer | Difference in immediate `MET_ALL` proportions, LearnLens minus comparator. State participant denominators and missing counts. |
| Conceptual understanding | Immediate concept criterion attainment, with baseline concept attainment as context. Report item profiles and a predefined count of met criteria. |
| Delayed retention, if approved | Delayed fresh-transfer attainment and conceptual criterion count at T3. Report the interval and immediate-to-delayed change by condition. |
| Feasibility | Consent uptake where approved aggregate counts exist, attendance, probe completion, retention, faults, and delivery fidelity. |
| Help and adaptation | Hint use, revisions, and selected activity reasons describe the learning process. They do not demonstrate independent understanding. |
| Technical feedback | Feedback quality, fallback, latency, token use, and cost remain separately labelled engineering measures. |

The criterion count is a research instrument summary, not a percentage grade or revived legacy score.
Freeze the criterion count, item mapping, scoring rules, and handling of mixed evidence before recruitment.
No minimum educationally meaningful difference has been approved.
The research lead must justify one before a confirmatory calculation or efficacy interpretation.

Two trained human reviewers independently rate the primary probe using the frozen anchors.
They also rate conceptual and delayed outcomes if included in the approved resource plan.
Train reviewers on approved non-study examples before they rate study evidence.
Keep original ratings, disagreements, and adjudication reasons. A third authorised reviewer resolves unresolved differences.
Missing evidence cannot become met through adjudication alone.
Report agreement before adjudication, with uncertainty and the approved statistic.

## 7. Blinding and AI assessment boundary

Outcome reviewers receive pseudonymous probe packets without condition, hint use, model output, or formal course results.
Shuffle packets and hide participant pairing and timepoint where the instrument permits.
Use shared layouts across conditions and remove condition labels from evidence metadata.
Reviewers may infer condition from student wording. Record each known blinding breach and its cause.
Keep the allocation key with the custodian until ratings and the analysis script are locked.
The analyst can use neutral arm labels until that lock is recorded.
Students and teaching staff cannot be fully blinded to the support interface. Disclose this limit.

D-07 selects validated AI suggestions for assessors as the eventual operational direction.
Before that separate gate passes, operational suggestions stay disabled and human assessment remains available.
The gate requires approved expert cases, error limits, fairness checks, measured results, and a release decision.
Feedback-judge thresholds, synthetic fixtures, and this protocol cannot substitute for that evidence.

The proposed research reviewers receive no AI assessment suggestions, including after operational activation.
This protects independent outcome measurement without reversing the selected operational direction.
Freeze operational AI availability for the study cohort and record the evaluator version.
A material activation or model change during collection requires a documented impact review and prospective amendment.
Do not pool changed conditions silently or treat a suggestion as a confirmed formal result.

## 8. Sample-size basis and stopping

No powered sample size is asserted. The available course count, participation rate, and study capacity are unknown.
The proposed first study prioritises feasibility and uncertainty estimates.
Its sample-size record must state the available eligible pool, expected consent, expected attrition, staff time, and recruitment cap.
Each assumption needs a source or a clear planning label.

For a rough precision illustration, let `n` be evaluable participants per arm.
At the conservative planning value of 0.5 in each arm, the standard error of a risk difference is approximately `sqrt(0.5/n)`.
An illustrative 95% normal half-width is `1.96 * sqrt(0.5/n)`.
This is an algebraic planning aid, not a final interval method or evidence about LearnLens.
Small samples need a suitable reviewed interval method; this approximation does not establish power.
Use `ceil(N_evaluable / (1 - anticipated_attrition))` only after the required inputs are justified.

If the study becomes confirmatory, the methods reviewer must approve a separate calculation before recruitment.
Record comparator success probability, meaningful difference, alpha, power, allocation ratio, attrition, and any clustering or multiplicity adjustment.
Keep the calculation script, source assumptions, and sensitivity range with the preregistration.
Do not borrow an effect size from a simulated learner study as human learning evidence.

Stop enrolment at the approved cap or closing date, whichever occurs first.
Do not extend recruitment after inspecting the treatment effect.
The research lead may pause collection for participant welfare, privacy incidents, unsafe feedback, or major technical faults.
Record the reason, affected sessions, institutional reporting route, and authority to resume.
There is no proposed interim efficacy or futility analysis.

## 9. Analysis, exclusions, and missingness

The target estimand is the difference in immediate fresh-transfer success under assignment to the two support packages.
Analyse participants by assigned condition wherever consent permits their data use.
Retain non-adherence, extra hints, slow work, and technical disruption in participant accounting.
For a feasibility study, the main estimate uses observed evaluable outcomes within assigned arms.
It does not recover the full assigned-population effect when outcomes are missing.
Report that limit alongside the missing-data bounds.

Report counts, proportions, risk difference, and a reviewed 95% interval for the primary endpoint.
The proposed interval method combines Wilson score intervals for independent proportions, following Newcombe.
The original paper describes this approach. [Newcombe, 1998](https://onlinelibrary.wiley.com/doi/abs/10.1002/%28SICI%291097-0258%2819980430%2917%3A8%3C873%3A%3AAID-SIM779%3E3.0.CO%3B2-I)
The methods reviewer must verify and freeze its implementation before preregistration.
Secondary criterion counts receive descriptive summaries and condition differences with uncertainty.
An adjusted model using baseline attainment is secondary only if the final sample supports it.
Do not add covariates after inspecting favourable results.

Use no confirmatory subgroup hypotheses in the proposed feasibility study.
Course, prior-experience band, and approved response mode may support descriptive checks where consent and cell size allow.
Suppression rules belong in the approved data plan.
Do not infer demographic fairness or subgroup efficacy from tiny cells or unavailable sensitive attributes.
Label all unregistered analyses exploratory and retain their rationale.

| Situation | Proposed rule |
| --- | --- |
| No valid consent or eligibility before allocation | Do not enrol. Use only approved aggregate screening counts, with no new identity linkage. |
| Duplicate enrolment discovered | Keep the earliest valid allocation and preserve an audit reason. Do not count two learners. |
| Ineligibility discovered after allocation | Record the flow count and reason. Apply the frozen eligibility rule without consulting outcomes. |
| Missing baseline | Retain an otherwise eligible participant in unadjusted analysis. Exclude only from analyses requiring that baseline. |
| Skipped or unevaluable mandatory probe item | Mark the endpoint missing with a reason. Do not assign zero, failure, or success. |
| Evaluated incorrect answer | Record `NOT_MET`; this is observed non-attainment, not missing data. |
| Technical interruption | Preserve accepted evidence. Use an approved fresh replacement only under the locked replacement rule. |
| Unapproved instructional aid during unaided probe | Flag contamination. Retain assigned-arm accounting and report a predeclared sensitivity exclusion. |
| Withdrawal | Stop new research collection and follow the approved scope for existing data. Do not override withdrawal for analysis. |
| Missed or late delayed follow-up | Record missing or outside-window status and actual interval. Never carry immediate performance forward. |

The replacement rule must name eligible fault categories, timing, and who authorises a fresh equivalent probe.
The default proposal permits replacement only when a fault prevents valid capture, before answer feedback is revealed.
Keep both attempt references and the reason. Never select the better answer from repeated valid research probes.
Lost evidence remains missing when no approved replacement applies.

Report a participant flow by condition: allocated, started, immediate observed, delayed observed, withdrawn, excluded, and missing.
Report field-level missingness, reasons, and technical failures separately from participant attrition.
Use no last-observation-carried-forward, automatic zero filling, or assumed pass.
For the binary primary endpoint, show extreme bounds treating missing outcomes as success or non-success in each arm.
Do not reconstruct withdrawn data that the approved withdrawal rule excludes.
Multiple imputation is not part of this feasibility proposal. Adding it requires a prespecified model and justified assumptions.

## 10. Approval and preregistration records

The research lead must obtain the required institutional ethics decision before recruitment.
Monash states that MUHREC reviews human research conducted by its staff or students.
The institution must determine the applicable review route for this study. [Monash Human Ethics](https://www.monash.edu/research-ethics-and-integrity/human-ethics)
This draft makes no exemption, risk-classification, or jurisdiction ruling.

BP12 also requires preregistration before recruitment.
Register the approved question, hypotheses, conditions, allocation, outcomes, instruments, sample-size basis, exclusions, missingness, group analyses, and deviation rules.
Retain the registry identifier, public or approved embargoed record, timestamp, and frozen document hashes.
Choose the registry and access arrangements through the research lead.
No registry entry has been created by this work.

| Required record | Accountable roles and known holder | Current evidence and blocking effect |
| --- | --- | --- |
| `T32-RQ` | Arv Surana, research lead; supervisor pending | Authoritative question or signed proposed wording absent; blocks protocol approval. |
| `T32-DESIGN` | Arv Surana, research lead; methods reviewer pending | Comparator, allocation, analysis, and sample-size basis need signed versions; blocks preregistration. |
| `T32-INSTRUMENTS` | Course lead, named assessor, accessibility reviewer | Sources, anchors, forms, tool rules, session timing, and replacement rule absent; blocks study use. |
| `T32-ETHICS` | Responsible investigator and institutional ethics authority | Decision identifier, scope, conditions, validity, and approved participant materials absent; blocks recruitment. |
| `T32-DATA` | Arv Surana, research lead; data owner, privacy and records advisers pending | Signed inventory, consent, storage, retention, withdrawal, and access records absent; blocks collection and export. |
| `T32-PREREG` | Arv Surana, research lead; supervisor pending | Registry identifier, timestamp, and approved version hashes absent; blocks recruitment. |
| `T32-RELEASE` | Arv Surana, research lead; course lead and operations owner pending | Named host approval and verified Task 33 enforcement absent; blocks live study activation. |
| `D07-VALIDATION` | Assessment governance and expert reviewers | Separate evaluator evidence and release record absent; blocks operational AI suggestions only. |

Each record needs a named owner, decision, date, version, scope, evidence location, conditions, and expiry where applicable.
Unfilled records remain pending. A role label, branch merge, passing test, or synthetic signature is not approval.
D-07 may remain closed while an otherwise approved human assessment study proceeds.
Study approval does not automatically open that separate gate.

## 11. Delivery evidence and change control

This delivery contains planning documents only. It creates no participant records, exports, or provider calls for research.
Task 33 owns enforceable study grants, consent, withdrawal, approved fields, and export controls.
The [existing restriction record](research-access-restriction.md) describes the blocked production research path.
Its historical pending-selection wording is superseded by the Task 8 approved selections; activation controls remain due.
This draft does not change application behaviour or claim that the proposed instruments are implemented.

Before study release, verify consent refusal and withdrawal leave course access and formal results intact.
Verify absent, revoked, expired, or wrong-study grants prevent research collection and export.
Verify probe packets preserve evidence while hiding condition and AI suggestions.
Verify support-stage boundaries, fresh forms, and no help-count penalty.
Verify assigned research condition cannot change operational access, teaching adaptation, learner-model updates, or assessment decision rules.
Use synthetic records only for these software checks, clearly labelled as synthetic evidence.

Record deviations with the old and new version, reason, timing, outcome visibility, scope, and decision owner.
Seek any required institutional amendment before changed procedures begin.
Freeze completed attempts under their original task and rule versions.
Report deviations and missingness by condition in the final study report.

Task 32 remains `PARTIAL` until the protocol and data plan receive their required decisions and preregistration.
Document review can finish before those external records exist. Recruitment cannot.
