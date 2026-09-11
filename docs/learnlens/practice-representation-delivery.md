# Reviewed practice representation delivery

This bounded FR35 delivery adds selectable reviewed content to ordinary formative practice. It complements the existing assessed supported-stage representation path. Generated representation candidates and new typed access forms for unaided transfer remain outside this delivery.

## Authoring and review

The task review editor stores up to twenty variants under `marking_criteria.practice_representations`. Each variant has a stable ID, format, brief/detailed declaration, actual text and optional steps/circuit, declared task source passages, construct-equivalence rationale, and a separate instructional/accessibility support declaration. Existing immutable `TaskRevision` snapshots and review events version the complete content; no new migration is needed.

Review validation rejects duplicate IDs, undeclared sources, missing rationale, invalid representation/circuit shapes, and contradictory support declarations. Accessibility-only content must declare instructional level 0; instructional variants declare levels 1–4, with worked examples requiring level 4. These checks validate structure and declarations. An authorised reviewer must still establish semantic equivalence and appropriate support for real content.

## Learner delivery

The self-only catalog lists metadata without releasing representation content or recording delivery evidence. Format and explanation-detail preferences select an available reviewed variant (format match first, then detail match); unavailable combinations are explained. Standard support opens the selected content automatically. On-request support waits for an explicit learner action. The learner can override the recommendation, and the latest override is retained for the same task revision and preference version. Disabling personalisation uses baseline text/brief preferences. Required task content and response requirements remain unchanged.

Delivery rechecks enrolment, course/task availability, prerequisite access, current task review and source approval/scan status. It rejects frozen assessed work, formal assessment declarations, transfer tasks and active fresh-application checks. During any unfinished transfer for that learner in the same course, the catalog withholds instructional variants and delivery rejects both new instructional requests and prior receipt replays. Reviewed level-zero access variants remain available; the selected variant cannot retain an instructional override while it is withheld. This uses the same course-transfer query as practice feedback and formal feedback release. Other learners/courses are unaffected, and submission of the exact transfer work ends this restriction. The practice panel is also excluded from the assessment/transfer workspace. Existing assessment and transfer support remains controlled by its own approved conditions.

The delivery mutation atomically saves an immutable evidence artifact before returning the selected content. It retains exact content, task revision and digest, review event, source approvals, preference version/values, selection mode, timestamp and support declaration. An exact retry returns the original receipt; a reused key with different input or changed review is rejected. Metadata reads create no evidence. Cookie-authenticated writes use the existing CSRF guard and a dedicated rate-limit bucket.

Practice responses conservatively carry all delivered support for that learner, task, course and task revision at or before the response time. Instructional levels are aggregated separately from access support, and delivery records are retained as evidence parents. This hook does not apply to frozen assessment work or staged transfer evidence. Opening content establishes delivery only; it does not establish learning, strategy success or a useful-format inference.

## Focused verification and integration

- Ten distinct backend cases passed in targeted runs of `tests/test_practice_representations.py`: reviewed preference selection, learner override and replay, exact provenance, response-time/revision/learner filtering, separate access and instructional support, changed/withdrawn review, malformed declarations/content, assessment-work exclusion, and API identity/CSRF boundaries. The initial cookie-CSRF test setup was corrected and that case rerun separately after the other nine passed.
- Six component cases passed in `PracticeRepresentationPanel.test.tsx`: actual preferred content, on-request keyboard override, disabled/stale review handling, retained override, late automatic-response protection and reapproval request renewal.
- TypeScript, scoped ESLint and scoped Ruff checks passed. No broad backend/frontend suite, browser run, real scanner execution or human accessibility/equivalence validation is claimed. Sources, approvals and scanner receipts used by tests are explicitly synthetic.

Coordinator integration owns combined API contract regeneration. The dedicated frontend wire types describe the new routes until that regeneration. The only shared hooks are API registration/security policy, task review validation, practice evidence aggregation, and task/review panel mounts. Migration 0052 remains unused by this package.

The cross-task transfer follow-up reproduced instructional POST delivery returning 200 during another task's active transfer. The focused regression now covers catalog filtering, new delivery/replay refusal without new evidence, preserved access delivery/replay, learner/course isolation and reopening after submission. It and the existing course-transfer practice/cached-feedback regression passed; the shared query extraction preserves the feedback boundary. No additional migration, frontend contract or broad suite run was needed.
