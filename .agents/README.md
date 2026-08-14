# LearnLens agent harness

This harness enforces one delivery path: ground, plan, implement, test, review locally, then request human PR review. Start with `harness.yaml` and `workflows/change-delivery.md`.

```text
.agents/
|-- harness.yaml        Roles, source order, states, and gates
|-- agents/             Four independent agent contracts
|-- skills/             Plans, PRs, commits, and skill creation
|-- hooks/              Before and after gate checks
|-- rules/              Delivery and product rules
|-- instructions/       Shared operating contract
|-- tools/
|   |-- mcp/            GitHub MCP contract
|   `-- connectors/     Git, gh, and CI contracts
|-- commands/           Stable workflow entry points
|-- workflows/          Delivery path and exact quality checks
|-- memory/             Reviewed project facts and decisions
|-- context/            Per-change evidence template
|-- permissions/        Read, write, publish, and approval policy
`-- guardrails/         Delivery and learner-safety blocks
```

The implementing agent cannot approve its own tests, correctness, or code quality. New commits make affected approvals stale.

Keep secrets, tokens, private user data, full learner answers, and generated runtime state out of this directory.
