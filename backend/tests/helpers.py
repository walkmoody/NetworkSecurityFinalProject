"""Shared helpers for backend tests."""

import json


def events(response) -> list[dict]:
    """Parse a streamed NDJSON response into its events."""
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def final(response) -> dict:
    """The last event of a stream: the result or the error."""
    return events(response)[-1]


def answers_for(quiz: dict) -> dict:
    """Valid (not necessarily correct) answers for every question in a public quiz."""
    by_type = {"multiple_choice": "A", "true_false": True,
               "open_ended": "A firewall filters traffic according to a security policy."}
    return {q["question_id"]: by_type[q["type"]] for q in quiz["questions"]}
