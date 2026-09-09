# Task 20 implementation plan

Base verified after fetch: `65a9457d27e849465e7f227471336552bb22b8b4`.
The learner model has an explicit-preference dimension, but no settings store or mounted editor exists.
EpisodeSupport already enforces supported hints and separate access support. TaskView retains required reflection and saved attempts.

## Contract chosen before implementation

Use global learner-owned settings because the consumers are workspace presentation controls across courses.
These are explicit choices, not learning evidence or estimates. No course, outcome, or diagnosis is invented.
Preference revisions provide their own action history; task actions continue through the existing evidence path.

`PreferenceValues`: pace `self_paced | stepwise`; format `text | stepwise`;
explanation_detail `brief | detailed`; breaks boolean; repeat_practice boolean;
personalisation_enabled boolean; support_amount `standard | on_request`;
feedback_form `inline | expandable`.
Defaults: self_paced, text, brief, false, false, true, standard, inline.
Only supported presentation options are offered. No audio, worked answer, or alternate assessment format is claimed.

GET `/learner-preferences/me` returns `{version, values}`; no write occurs during reads.
PUT at the same path accepts `{expected_version, request_key, values}`.
POST `/learner-preferences/me/reset` accepts `{expected_version, request_key}` and appends defaults.
GET `/learner-preferences/me/history` returns descending revisions with bounded offset pagination.
Each revision contains version, values, action (save/reset), and server timestamp.
Identity comes only from authentication. Unknown fields and queries are rejected.
The initial version is zero. Unique learner/version and learner/request keys prevent competing heads and duplicate requests.
An exact retry returns its original receipt; changed key payloads and stale saves return 409.
Reset never deletes history. Failure rolls back; UI preserves drafts and requires explicit conflict refresh before resaving.

Effective presentation uses baseline values and an explicit disabled flag when personalisation is disabled.
Task/stage conditions retain final authority. Transfer suppresses optional instructional effects and practice prompts.
Access support, required feedback, response fields, and reflection remain available under every setting.
Presentation never modifies assessment conditions, results, source release, or response storage.

## Requirement and test links

| Requirement | Implementation | Planned proof |
| --- | --- | --- |
| FR35, FR37 persistence and correction | append-only preferences, mounted editor | service/API persistence, reset, replay, concurrent sessions, history protection |
| FR37 ownership and opt-out | authenticated self routes, baseline effective defaults | actor/field denial, CSRF, UI opt-out and reload |
| FR35 bounded effects | workspace navigation, optional guidance, breaks, saved-practice review, support disclosure | component and authenticated browser effects |
| FR36 reflection | existing fields stay mounted | transfer and opt-out regressions |
| NFR31 explicit choices only | typed fields, separate archive | reject sensitive/free-text fields, unchanged evidence/model/result history |
| Recovery and access | retained draft, conflict refresh, labelled native controls | failure retry, keyboard, Axe, reflow |

Coordinator owns migration 0033, model registration, mounted router, API client, generated contracts, integration and gates.
Run full CI-equivalent checks and separate Standards, Spec, and Test Judge self-reviews before marking complete.
The current instruction prohibits sub-agents. No independent agent verdict is claimed.
No commit, push, merge, diagnostics, pathway, tutor, or AI assessment activation is part of this implementation request.
