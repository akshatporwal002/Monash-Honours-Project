---
name: create-agent-skill
description: Create or update concise project-local skills under .agents/skills with valid metadata, focused instructions, optional resources, and validation. Use when adding a reusable agent capability, turning a repeated workflow into a skill, or repairing an existing harness skill.
---

# Create Agent Skill

Build skills from real repeated work, not imagined tool contracts.

## Define the skill

Identify concrete trigger phrases, expected inputs, outputs, failure cases, and actions. Inspect related project files and existing skills before choosing the workflow.

Name the folder with lowercase letters, digits, and hyphens. Prefer a short verb-led name under 64 characters.

## Initialize and edit

Use the available skill initializer when creating a new skill. Place project skills under `.agents/skills/<skill-name>`.

Keep only:

- `SKILL.md` with `name` and `description` frontmatter.
- `agents/openai.yaml` with matching interface metadata.
- `scripts`, `references`, or `assets` only when the skill needs them.

Do not add a README, changelog, install guide, or duplicate reference text inside a skill folder.

Write the description as the full trigger rule. Write the body as direct steps for another agent. Keep core instructions short and link one level deep to detailed references.

## Protect this harness

Ground project claims in the three controlling files under `docs` and actual code under `src-main`. Do not copy another project's branches, paths, commands, business rules, or tools without verifying them here.

Skills cannot grant themselves more permission. Keep GitHub writes, destructive actions, external messages, production changes, and secret access behind the project permission policy.

## Validate

Run the skill creator's `quick_validate.py` against the finished folder. Search for placeholder text such as `TODO`. Read every referenced file and verify each relative link. Run any bundled script with a representative safe input.

Report validation output and any behaviour that still needs a real forward test.
