"""Offline, source-excerpt exercises; educators still review content and validity."""

import json
from random import SystemRandom
from uuid import uuid4

_shuffle = SystemRandom().shuffle


def display_order(items):
    ordered = list(items)
    _shuffle(ordered)
    return ordered


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
        {"id": str(uuid4()), "text": text, "source_references": [source["chunk_id"]]}
        for text in fragments
    ]
    if task_type == "sequencing":
        definition = {"task_type": task_type, "items": display_order(items)}
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
                "id": str(uuid4()),
                "text": "Excerpt beginning: " + openings[i],
            }
            for i, item in enumerate(items)
        ]
        definition = {
            "task_type": task_type,
            "prompts": display_order(prompts),
            "options": display_order(items),
        }
        response = {
            "schema_version": "learnlens.matching-response.v1",
            "pairs": {
                prompt["id"]: item["id"] for prompt, item in zip(prompts, items, strict=True)
            },
        }
    definition["schema_version"] = f"learnlens.{task_type}.v1"
    return json.dumps(response), {"structured_task": definition, "response_review": "human"}
