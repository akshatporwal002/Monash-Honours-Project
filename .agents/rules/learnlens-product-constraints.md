# LearnLens product constraints

Every agent must protect these controlling rules:

- Learner assessment results are only `PASS` and `INCOMPLETE`.
- Learner-facing assessment must not show `FAIL` or numeric formal grades.
- The assessor sets and approves the Bloom target, criteria, pass rule, and versions before the attempt.
- Automated evaluation may be provisional. Formal confirmation needs an authorised assessor.
- The Quality Judge uses its own result namespace. It is not learner assessment.
- Confidence, time, attempts, hints, access support, research state, model estimates, and game points cannot lower a formal result.
- Access support stays separate from instructional support and preserves the target standard.
- Evidence, inference, activity state, formal results, and research data stay distinct.
- Important decisions retain evidence, rule, task, model, actor, reason, and time.
- Accepted learner work survives model, retrieval, Qiskit, worker, and network faults.
- Course and learner scope is enforced in services and queries, not only the UI.
- General logs exclude direct student IDs, secrets, prompts, stack traces, and unneeded full answers.
- Missing pilot policy remains visible configuration or an open decision. Agents do not invent it.

Use exact FR, PD, BP, NFR, AC, and AT references from the controlling docs in plans and findings.
