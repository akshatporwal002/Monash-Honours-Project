# Delivery gates

- Block implementation when the grounding record or durable plan is missing.
- Block unplanned scope. Update the plan before adding work.
- Block step completion when its acceptance line lacks current proof.
- Block test approval when commands failed, did not run, or used stale code.
- Block local approval when a reviewer has an open blocking finding.
- Block human PR review when any local verdict or required GitHub check is missing.
- Invalidate affected verdicts after any new commit or force-updated head.
- Block merge and deployment because this workflow ends at review readiness.

Report a blocked gate as: gate, evidence, owner, and next action. Never turn a block into a warning to move forward.
