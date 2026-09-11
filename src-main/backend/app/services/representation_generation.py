"""Build and validate source-aware alternatives without approving or delivering them."""

import re
from copy import deepcopy

from app.schemas.episode import EpisodePlanV1
from app.schemas.representation_generation import GeneratedRepresentations
from app.schemas.support_representations import AccessRepresentation, SupportRepresentation


def validate_generated_representations(value, source_texts, task_sources):
    candidate = GeneratedRepresentations.model_validate(value)
    for item in candidate.variants:
        if not set(item.source_references) <= set(task_sources):
            raise ValueError("Generated representations must cite this task's declared sources")
        for quote in item.source_quotes:
            if not quote.quote.strip() or quote.quote not in source_texts.get(
                quote.source_reference, ""
            ):
                raise ValueError(
                    "Generated representation quotes must exactly match supplied sources"
                )
    return candidate


def local_representation_candidates(task, sources, *, access_only=False):
    """Extract real source content and preserve task inputs; do not invent a solved example."""
    declared = set(task.get("source_references") or [])
    rows = [
        (str(row["chunk_id"]), row["text"])
        for row in sources
        if row.get("chunk_id") in declared
        and isinstance(row.get("text"), str)
        and row["text"].strip()
    ]
    if not rows:
        raise ValueError("Representation generation requires the task's actual source passages")
    # Keep exact substrings for validation and provenance, including original whitespace.
    excerpts = [(reference, text.strip()[:900]) for reference, text in rows[:2]]
    quotes = [{"source_reference": ref, "quote": text} for ref, text in excerpts]
    references = [ref for ref, _ in excerpts]
    prompt = str(task.get("prompt") or task.get("description") or "").strip()
    instructions = str(task.get("instructions") or "").strip()
    if not prompt or not instructions:
        raise ValueError(
            "Representation generation requires the actual task prompt and instructions"
        )
    variants = []

    def add(
        identity, mode, detail, text, steps=(), *, circuit=None, access=False, source_quotes=quotes
    ):
        if access_only and not access:
            return
        variants.append(
            {
                "representation_id": identity,
                "mode": mode,
                "title": f"{'Task access' if access else 'Source support'}: {mode.replace('_', ' ')} ({detail})",
                "text": text,
                "steps": list(steps),
                "circuit": circuit,
                "explanation_detail": detail,
                "support_kind": "accessibility" if access else "instructional",
                "instructional_support_level": 0
                if access
                else 4
                if mode == "worked_example"
                else 2,
                "source_references": list(
                    dict.fromkeys(q["source_reference"] for q in source_quotes)
                ),
                "source_quotes": source_quotes,
                "equivalence_basis": (
                    "Draft: preserves the supplied task input and required response without a solution or instructional cue. Verify construct equivalence before review approval."
                    if access
                    else "Draft: presents cited source content alongside the unchanged task. Verify factual alignment, construct equivalence and the declared instructional support before review approval."
                ),
            }
        )

    brief = f"Source passage:\n{excerpts[0][1]}"
    detailed = "\n\n".join(
        f"Source passage {index + 1}:\n{text}" for index, (_, text) in enumerate(excerpts)
    )
    detailed += f"\n\nTask to connect with the source:\n{prompt[:900]}\n\nRequired response:\n{instructions[:900]}"
    add("source-text-brief", "text", "brief", brief, source_quotes=quotes[:1])
    add("source-text-detailed", "text", "detailed", detailed)
    steps = [
        f"Task: {prompt[:900]}",
        *[f"Source: {text}" for _, text in excerpts],
        f"Required response: {instructions[:900]}",
    ]
    add(
        "source-stepwise-brief",
        "stepwise",
        "brief",
        brief,
        [steps[0], steps[1], steps[-1]],
        source_quotes=quotes[:1],
    )
    add("source-stepwise-detailed", "stepwise", "detailed", detailed, steps)
    add("source-visual", "visual", "detailed", detailed, steps)
    unavailable = []
    example = next(
        (
            (ref, text)
            for ref, text in rows
            if re.search(r"\b(?:worked\s+example|example\s*:)", text, re.I)
        ),
        None,
    )
    if example:
        ref, text = example
        excerpt = text.strip()[:3500]
        add(
            "source-worked-example",
            "worked_example",
            "detailed",
            excerpt,
            source_quotes=[{"source_reference": ref, "quote": excerpt}],
        )
    else:
        unavailable.append(
            {
                "mode": "worked_example",
                "reason": "No labelled worked example occurs in the supplied task sources. A reviewer or configured model must author and source one before it can be offered.",
            }
        )
    # Access alternatives reproduce the public task, never its private marking guidance.
    access_text = f"{prompt}\n\n{instructions}"
    code = task.get("starter_code")
    if isinstance(code, str) and code:
        access_text += f"\n\n{code}"
    if len(access_text) <= 4000:
        add("task-access-text", "text", "detailed", access_text, access=True)
        access_steps = [prompt, instructions, *([code] if isinstance(code, str) and code else [])]
        if all(len(step) <= 1000 for step in access_steps):
            add(
                "task-access-stepwise",
                "stepwise",
                "detailed",
                access_text,
                access_steps,
                access=True,
            )
            add("task-access-visual", "visual", "detailed", access_text, access_steps, access=True)
    circuit = (task.get("marking_criteria") or {}).get("starter_circuit")
    if isinstance(circuit, dict) and len(access_text) <= 4000:
        add(
            "task-access-circuit",
            "circuit",
            "detailed",
            access_text,
            circuit=deepcopy(circuit),
            access=True,
        )
    else:
        unavailable.append(
            {
                "mode": "circuit",
                "reason": "The task has no bounded circuit input to reproduce. A circuit alternative needs construct-specific authoring and review.",
            }
        )
    offered = {item["mode"] for item in variants}
    reasons = {item["mode"]: item["reason"] for item in unavailable}
    unavailable = [
        {
            "mode": mode,
            "reason": reasons.get(
                mode,
                "This format cannot preserve the complete task input within the reviewed access contract. Author an appropriate equivalent form before release.",
            ),
        }
        for mode in ("text", "visual", "worked_example", "circuit", "stepwise")
        if mode not in offered
    ]
    if access_only:
        next(item for item in unavailable if item["mode"] == "worked_example")["reason"] = (
            "Worked examples supply instructional help and cannot be offered as unaided transfer access."
        )
    return validate_generated_representations(
        {"variants": variants, "unavailable_modes": unavailable},
        dict(rows),
        references + [ref for ref, _ in rows],
    )


def bind_generated_representation_sources(candidate, mapping):
    """Keep content and its grounding aligned when retrieval IDs become passage IDs."""
    value = deepcopy(candidate)
    for variant in value["variants"]:
        variant["source_references"] = [mapping[ref] for ref in variant["source_references"]]
        for quote in variant["source_quotes"]:
            quote["source_reference"] = mapping[quote["source_reference"]]
    return GeneratedRepresentations.model_validate(value)


def attach_generated_task_representations(output, sources, *, provider=None, model=None):
    """Generation-entry-point hook: return a copied task with validated draft alternatives.

    A configured provider may supply marking_criteria.representation_candidates for
    the ordinary/supported task and transfer_access_candidates for transfer. Missing
    candidates use the explicit local source-extraction builder. No approval occurs.
    """
    task = deepcopy(output)
    criteria = task.setdefault("marking_criteria", {})
    source_texts = {row["chunk_id"]: row["text"] for row in sources}
    plan = (
        EpisodePlanV1.model_validate(criteria["episode_plan"])
        if criteria.get("episode_plan")
        else None
    )
    scopes = ("supported", "transfer") if plan else ("practice",)
    generations = {}
    for target in scopes:
        context = deepcopy(task)
        if target == "transfer":
            context.update(
                prompt=plan.transfer.prompt,
                instructions=plan.transfer.instructions,
                starter_code=plan.transfer.starter_code,
                marking_criteria={"starter_circuit": plan.transfer.starter_circuit},
            )
        key = "transfer_access_candidates" if target == "transfer" else "representation_candidates"
        raw = criteria.pop(key, None)
        if raw is not None and (not provider or not model):
            raise ValueError("Provider identity is required for supplied representation candidates")
        access_only = target == "transfer" or task.get("task_type") == "transfer"
        candidate = (
            validate_generated_representations(raw, source_texts, task["source_references"])
            if raw is not None
            else local_representation_candidates(context, sources, access_only=access_only)
        )
        if access_only and any(item.support_kind != "accessibility" for item in candidate.variants):
            raise ValueError("Generated transfer alternatives cannot provide instructional help")
        installed = {}
        if target == "practice":
            installed["practice"] = [item.reviewed_content() for item in candidate.variants]
            criteria["practice_representations"] = installed["practice"]
        else:
            target_plan = (
                criteria["episode_plan"]["transfer"]
                if target == "transfer"
                else criteria["episode_plan"]
            )
            for kind, field, schema in (
                ("accessibility", "access_representations", AccessRepresentation),
                ("instructional", "support_representations", SupportRepresentation),
            ):
                if target == "transfer" and kind == "instructional":
                    continue
                items = [
                    schema.model_validate(
                        {
                            key: value
                            for key, value in item.reviewed_content().items()
                            if key not in {"representation_id", "support_kind"}
                        }
                    ).model_dump(mode="json")
                    for item in candidate.variants
                    if item.support_kind == kind
                ]
                target_plan[field] = items
                installed[field] = items
        generations[target] = {
            "candidate": candidate.model_dump(mode="json"),
            "installed": deepcopy(installed),
            "provider": provider if raw is not None else "local-deterministic",
            "model": model if raw is not None else "source-representation-extract-v1",
        }
    criteria["representation_generation"] = generations
    if plan:
        criteria["episode_plan"] = EpisodePlanV1.model_validate(
            criteria["episode_plan"]
        ).model_dump(mode="json")
        if "multipart_candidate" in criteria:
            criteria["multipart_candidate"]["episode_plan"] = deepcopy(criteria["episode_plan"])
    if isinstance(criteria.get("generation_design"), dict):
        criteria["generation_design"]["equivalent_formats"] = sorted(
            {
                item["mode"]
                for generation in generations.values()
                for item in generation["candidate"]["variants"]
            }
        )
    return task


def bind_task_representation_sources(criteria, mapping):
    """Generation binding hook for all installed variants and immutable candidate quotes."""
    result = deepcopy(criteria)

    def bind_items(items):
        for item in items:
            item["source_references"] = [mapping[ref] for ref in item["source_references"]]

    bind_items(result.get("practice_representations", []))
    if result.get("episode_plan"):
        plan = result["episode_plan"]
        bind_items(plan.get("support_representations", []))
        bind_items(plan.get("access_representations", []))
        bind_items(plan["transfer"].get("access_representations", []))
        if "multipart_candidate" in result:
            result["multipart_candidate"]["episode_plan"] = deepcopy(plan)
    for generation in result.get("representation_generation", {}).values():
        generation["candidate"] = bind_generated_representation_sources(
            generation["candidate"], mapping
        ).model_dump(mode="json")
        for items in generation["installed"].values():
            bind_items(items)
    return result
