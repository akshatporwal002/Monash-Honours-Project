# Evidence-first delivery rule

No implementation begins until the grounding record and durable plan exist.

| Gate | Required evidence | Failure response |
| --- | --- | --- |
| Grounded | Source files, current code path, tests, CI, worktree, gaps | Stop planning claims that lack proof. Mark them `UNVERIFIED`. |
| Planned | Numbered file in `docs/plans`, step checklists, step acceptance, test strategy | Do not edit implementation files. |
| Implemented | Diff maps to plan steps and contains no unrelated work | Return the diff to implementation. |
| Tested | Targeted and required release checks, with exact results and limits | Keep the PR draft. |
| Locally reviewed | Three independent reviewer verdicts pass | Keep the PR draft and fix findings. |
| PR ready | Plan-matched body and current GitHub checks pass | Do not request human review. |

New evidence may require the plan to change. Update the plan before changing implementation scope.
