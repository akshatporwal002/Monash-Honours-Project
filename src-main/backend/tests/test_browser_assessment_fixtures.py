"""Browser seeds remain private while mounted review routes enforce real rules."""

from collections.abc import Generator

import pytest
from browser_e2e_server import _build_app
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def browser_client(tmp_path_factory: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    database = tmp_path_factory.mktemp("browser-fixtures") / "test.db"
    app = _build_app(f"sqlite:///{database.as_posix()}")
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.state.browser_e2e_cleanup()


def _login(client: TestClient, context: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": context["educator_email"], "password": context["educator_password"]},
    )
    assert response.status_code == 200
    assert [assignment["course_id"] for assignment in response.json()["scoped_assignments"]] == [
        context["course_id"]
    ]


@pytest.mark.parametrize(
    ("action", "new_result", "result_state"),
    [
        ("WITHHOLD", None, "PROVISIONAL"),
        ("RETURN", None, "PROVISIONAL"),
        ("CONFIRM", None, "CONFIRMED"),
        ("OVERRIDE", "INCOMPLETE", "OVERRIDDEN"),
    ],
)
def test_each_review_action_has_private_records_and_real_guards(
    browser_client: TestClient, action: str, new_result: str | None, result_state: str
) -> None:
    first_response = browser_client.post("/e2e/assessment-review-fixture")
    second_response = browser_client.post("/e2e/assessment-review-fixture")
    assert first_response.status_code == second_response.status_code == 200
    first, second = first_response.json(), second_response.json()
    for key in ("course_id", "attempt_id", "response_id", "decision_id", "educator_email"):
        assert first[key] != second[key]

    _login(browser_client, first)
    queue = browser_client.get(f"/api/v1/assessment/courses/{first['course_id']}/review-queue")
    assert queue.status_code == 200
    assert [record["decision_id"] for record in queue.json()] == [first["decision_id"]]
    assert queue.json()[0]["result_state"] == "PROVISIONAL"
    assert queue.json()[0]["review_revision"] == 0

    other_url = f"/api/v1/assessment/decisions/{second['decision_id']}/review"
    payload = {
        "action": action,
        "reason": "Review the frozen evidence for this isolated browser execution.",
        "expected_result_state": "PROVISIONAL",
        "expected_review_revision": 0,
        "new_result": new_result,
    }
    assert browser_client.get(other_url).status_code == 404
    assert browser_client.post(other_url, json=payload).status_code == 404
    assert (
        browser_client.get(
            f"/api/v1/assessment/courses/{second['course_id']}/review-queue"
        ).status_code
        == 404
    )

    own_url = f"/api/v1/assessment/decisions/{first['decision_id']}/review"
    invalid_override = {**payload, "action": "OVERRIDE", "new_result": "PASS"}
    assert browser_client.post(own_url, json=invalid_override).status_code == 422
    result = browser_client.post(own_url, json=payload)
    assert result.status_code == 200
    assert result.json()["result_state"] == result_state
    assert result.json()["review_revision"] == 1
    replay = browser_client.post(own_url, json=payload)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["review_revision"] == 1
    assert len(browser_client.get(own_url).json()["history"]) == 1
    if action == "CONFIRM":
        already_confirmed = {
            **payload,
            "expected_result_state": "CONFIRMED",
            "expected_review_revision": 1,
        }
        assert browser_client.post(own_url, json=already_confirmed).status_code == 422

    _login(browser_client, second)
    untouched = browser_client.get(other_url)
    assert untouched.status_code == 200
    assert untouched.json()["result_state"] == "PROVISIONAL"
    assert untouched.json()["review_revision"] == 0
    assert untouched.json()["history"] == []


def test_authoring_accounts_do_not_accumulate_other_tests_assignments(
    browser_client: TestClient,
) -> None:
    first_response = browser_client.post("/e2e/assessment-authoring-fixture")
    second_response = browser_client.post("/e2e/assessment-authoring-fixture")
    assert first_response.status_code == second_response.status_code == 200
    first, second = first_response.json(), second_response.json()
    for key in ("course_id", "outcome_id", "task_id", "educator_email"):
        assert first[key] != second[key]
    _login(browser_client, first)
    _login(browser_client, second)


def test_browser_seed_routes_are_absent_from_the_production_application() -> None:
    assert not any(path.startswith("/e2e/") for path in create_app().openapi()["paths"])
