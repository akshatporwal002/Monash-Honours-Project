"""Offline, source-excerpt exercises; educators still review content and validity."""

import json


def grounded_structure(task_type, sources):
    source = next((row for row in sources if str(row.get("text", "")).strip()), None)
    if source is None:
        raise ValueError("Structured generation needs a source passage")
    words = source["text"].split()[:200]
    if len(words) < 6:
        raise ValueError("The source passage is too short for a structured exercise")
    midpoint = len(words) // 2
    fragments = [" ".join(words[:midpoint]), " ".join(words[midpoint:])]
    if len(set(fragments)) != len(fragments):
        raise ValueError("The source needs distinguishable excerpts for this exercise")
    items = [
        {"id": f"item-{i + 1}", "text": text, "source_references": [source["chunk_id"]]}
        for i, text in enumerate(fragments)
    ]
    if task_type == "sequencing":
        definition = {"task_type": task_type, "items": list(reversed(items))}
        response = {
            "schema_version": "learnlens.sequencing-response.v1",
            "order": [item["id"] for item in items],
        }
    else:
        openings = [" ".join(fragment.split()[:3]) for fragment in fragments]
        if len(set(openings)) != len(openings):
            openings = fragments
        prompts = [
            {
                **item,
                "id": f"prompt-{i + 1}",
                "text": "Excerpt beginning: " + openings[i],
            }
            for i, item in enumerate(items)
        ]
        definition = {"task_type": task_type, "prompts": prompts, "options": list(reversed(items))}
        response = {
            "schema_version": "learnlens.matching-response.v1",
            "pairs": {
                prompt["id"]: item["id"] for prompt, item in zip(prompts, items, strict=True)
            },
        }
    definition["schema_version"] = f"learnlens.{task_type}.v1"
    return json.dumps(response), {"structured_task": definition, "response_review": "human"}
