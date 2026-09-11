"""Conservative, inspectable dialogue cues; no misconduct or achievement inference."""

import re

COPIED_SOLUTION = re.compile(
    r"\bI (?:copied|pasted) (?:this|the|a) (?:answer|solution)\b|\bas an AI language model\b",
    re.I,
)


def dialogue_cue(message, previous_turns, answer_seeking):
    repeated = [turn.id for turn in previous_turns if answer_seeking.search(turn.learner_text)]
    kinds = []
    if answer_seeking.search(message) and repeated:
        kinds.append("REPEATED_ANSWER_ONLY_REQUEST")
    if COPIED_SOLUTION.search(message):
        kinds.append("COPIED_SOLUTION_LANGUAGE")
    if not kinds:
        return None
    return {
        "rule_version": "dialogue-review-cues-v1",
        "signals": kinds,
        "related_turn_ids": repeated if "REPEATED_ANSWER_ONLY_REQUEST" in kinds else [],
        "interpretation": "Uncertain review cue. Quotation, permitted assistance, or other context may explain this language.",
        "next_action": "Ask for the learner's reasoning or a fresh application; review the retained dialogue.",
        "assessment_effect": "none",
    }
