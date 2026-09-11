"""Canonical choice definitions and new response validation; never rewrites history."""

import json

CHOICE_TYPES = {"quiz", "multiple_choice", "multiple_answer"}


def choice_ids(task_type, criteria):
    if task_type not in CHOICE_TYPES:
        return None
    choices = criteria.get("choices") if isinstance(criteria, dict) else None
    if not isinstance(choices, list) or len(choices) < 2:
        raise ValueError("Choice tasks require at least two reviewed choices")
    identifiers = set()
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("Each choice requires a string identifier and text")
        identifier, label = choice.get("id"), choice.get("text")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier != identifier.strip()
            or identifier in identifiers
        ):
            raise ValueError(
                "Choice identifiers must be nonblank, unique strings without surrounding spaces"
            )
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Each choice requires nonblank text")
        identifiers.add(identifier)
    return identifiers


def choice_response(task_type, criteria, answer, *, complete):
    identifiers = choice_ids(task_type, criteria)
    if identifiers is None:
        return None
    if answer == "" and not complete:
        return set()
    if task_type == "multiple_answer":
        try:
            selected = json.loads(answer)
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Multiple-answer responses require a JSON array of choice identifiers"
            ) from error
        if not isinstance(selected, list) or any(not isinstance(value, str) for value in selected):
            raise ValueError("Multiple-answer responses require a JSON array of string identifiers")
        if len(set(selected)) != len(selected):
            raise ValueError("Select each choice at most once")
    else:
        selected = [answer]
    if complete and not selected:
        raise ValueError("Select at least one reviewed choice")
    if any(value not in identifiers for value in selected):
        raise ValueError("Select only exact identifiers from the reviewed choices")
    return set(selected)


def validate_choice_key(task_type, criteria, expected_answer):
    if choice_ids(task_type, criteria) is None:
        return
    expected = None
    if expected_answer is not None:
        expected = choice_response(task_type, criteria, expected_answer, complete=True)
    if task_type == "multiple_answer" and "correct_answers" in criteria:
        correct = choice_response(
            task_type, criteria, json.dumps(criteria["correct_answers"]), complete=True
        )
        if expected is not None and expected != correct:
            raise ValueError("The answer key and correct_answers must identify the same choices")
