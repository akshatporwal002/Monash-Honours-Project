# Hooks

These hooks are mandatory lifecycle checklists. The current harness treats them as declarative gates. A future runner may automate them without changing their meaning.

- `before-implementation.md` blocks code changes until grounding and planning exist.
- `after-implementation.md` routes completed steps to test evidence.
- `before-review-request.md` blocks PR review until all local and CI gates pass.
