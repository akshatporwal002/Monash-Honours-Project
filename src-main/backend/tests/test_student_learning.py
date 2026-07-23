from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.main import create_app


def client_for(db_session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


def test_dashboard_seeds_tasks_and_progress(db_session: Session) -> None:
    response = client_for(db_session).get("/api/v1/students/demo")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["progress"]["total_tasks"] == 4
    assert dashboard["tasks"][0]["title"] == "Qubits & superposition"
    assert dashboard["recommendations"][0]["priority"] == "high"
    assert len(dashboard["notifications"]) == 1


def test_submit_task_updates_points_progress_and_achievements(db_session: Session) -> None:
    client = client_for(db_session)
    dashboard = client.get("/api/v1/students/demo").json()
    student_id = dashboard["progress"]["student_id"]
    task = dashboard["tasks"][0]
    response = client.put(
        f"/api/v1/students/{student_id}/tasks/{task['id']}/submission",
        json={"answer": "A qubit can exist in superposition until measurement.", "submit": True},
    )
    assert response.status_code == 200
    assert response.json()["score"] == 100
    refreshed = client.get(f"/api/v1/students/{student_id}/dashboard").json()
    assert refreshed["progress"]["completed_tasks"] == 1
    assert refreshed["progress"]["points"] == 100
    assert {item["code"] for item in refreshed["progress"]["achievements"]} == {
        "first-step", "perfect-score"
    }


def test_simulate_bell_state(db_session: Session) -> None:
    client = client_for(db_session)
    student_id = client.get("/api/v1/students/demo").json()["progress"]["student_id"]
    response = client.post(
        f"/api/v1/students/{student_id}/simulate",
        json={"qubits": 2, "operations": [
            {"gate": "h", "targets": [0]}, {"gate": "cx", "targets": [0, 1]}
        ], "shots": 1024},
    )
    assert response.status_code == 200
    assert response.json()["probabilities"] == {"00": 0.5, "11": 0.5}


def test_simulation_rejects_invalid_target(db_session: Session) -> None:
    client = client_for(db_session)
    student_id = client.get("/api/v1/students/demo").json()["progress"]["student_id"]
    response = client.post(f"/api/v1/students/{student_id}/simulate", json={
        "qubits": 1, "operations": [{"gate": "x", "targets": [2]}]
    })
    assert response.status_code == 422


def test_educator_can_monitor_student_progress(db_session: Session) -> None:
    response = client_for(db_session).get("/api/v1/students/educator-progress")
    assert response.status_code == 200
    students = response.json()
    assert students[0]["display_name"] == "Alex Morgan"
    assert students[0]["total_tasks"] == 4
