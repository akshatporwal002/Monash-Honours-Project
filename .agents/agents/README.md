# Agents

The harness uses four independent roles:

1. `github-workflow-agent.md` manages branches, commits, draft PRs, checks, and review readiness.
2. `test-judge-agent.md` decides whether test evidence proves the plan acceptance rules.
3. `code-reviewer-agent.md` reviews correctness, security, data safety, and LearnLens rules.
4. `code-quality-reviewer-agent.md` reviews maintainability, types, structure, and static quality.

The implementing agent cannot issue any reviewer verdict. A PR remains draft until all required verdicts pass.
