# After implementation hook

Run after each plan step changes implementation files.

- Compare the diff with the active plan step.
- Remove no user-owned or unrelated change.
- Update generated contracts and docs when the step requires them.
- Run the smallest relevant test and static check.
- Record the exact command, result, and limit.
- Mark the step complete only when its acceptance line is proved.

If the diff changes scope, update and review the plan before continuing.
