"""Deterministic fake HTTP transport: orchestration evidence only, no provider calls."""

import asyncio
import copy
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

from .adapter import LearningLoop

FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/task38_benchmark/episode.json"


def roster(count):
    template = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [
        {
            **copy.deepcopy(template),
            "student_email": f"task38-{n}@example.invalid",
            "student_password": "synthetic-fixture-only",
            "task_id": f"task38-task-{n}",
            "course_id": f"task38-course-{n}",
            "form_id": f"task38-form-{n}",
        }
        for n in range(count)
    ]


class FakeTransport:
    def __init__(self, identity="fake", confirmed=False, feedback_status="validated"):
        self.identity, self.confirmed, self.feedback_status = identity, confirmed, feedback_status
        self.now = 0.0
        self.calls = []
        self.draft = None
        self.submissions = []
        self.polls = {}
        self.transferred = False
        self.admin = False
        self.settings = {"llm_provider": "local", "llm_model": "template"}

    def uid(self, suffix):
        return str(uuid5(NAMESPACE_URL, self.identity + suffix))

    async def sleep(self, duration):
        self.now += duration
        await asyncio.sleep(0)

    def handle(self, request):
        self.now += 0.05
        path = request.url.path.removeprefix("/api/v1/")
        body = json.loads(request.content) if request.content else None
        method = request.method
        self.calls.append((method, path, copy.deepcopy(body)))

        def reply(value, status=200, headers=None):
            return httpx.Response(status, json=value, headers=headers)

        if path == "auth/login":
            self.admin = body["email"].startswith("admin")
            return reply(
                {"id": self.uid(":actor"), "role": "administrator" if self.admin else "student"},
                headers={"set-cookie": "ql_csrf=fake-csrf; Path=/"},
            )
        if method != "GET" and request.headers.get("x-csrf-token") != "fake-csrf":
            return reply({}, 403)
        if path == "admin/settings":
            if not self.admin:
                return reply({}, 403)
            if method == "PUT":
                self.settings.update(body)
            return reply(self.settings)
        if path.endswith("/dashboard") or path.startswith("progress/"):
            return reply({})
        if path.endswith("/draft"):
            if method == "PUT":
                self.draft = copy.deepcopy(body)
            return reply(self.draft)
        if path.endswith("/start"):
            return reply({"assessment_work_start_id": self.uid(":start")})
        if path.endswith("/episode/help"):
            if self.transferred:
                return reply({}, 403)
            return reply({"record": {"id": self.uid(":hint")}, "content": "Conceptual hint"})
        if path.endswith("/episode/checkpoints"):
            self.draft = copy.deepcopy(body["response"])
            checkpoint = self.uid(":checkpoint:" + body["part_id"])
            stage = (
                self.draft["episode"]["transfer"]["process"]
                if self.transferred
                else self.draft["episode"]["supported"]
            )
            stage["prediction_checkpoint_id"] = checkpoint
            return reply({"checkpoint_id": checkpoint, "draft": self.draft})
        if path.endswith("/episode/transfer"):
            self.transferred = True
            return reply(
                {"transfer": {"part_id": "transfer", "stage_start_id": self.uid(":transfer")}}
            )
        if path == "students/me/simulate":
            return reply(
                {
                    "status": "completed",
                    "run_id": self.uid(":sim:" + body["episode_part_id"]),
                    "circuit_version_id": self.uid(":circuit:" + body["episode_part_id"]),
                }
            )
        if path.endswith("/submissions") and path.startswith("students/"):
            if method == "GET":
                return reply(self.submissions)
            if "/task38-next/" in path and not (body.get("episode") or {}).get("supported", {}).get(
                "explanation"
            ):
                return reply({"detail": "This response type requires typed episode evidence"}, 422)
            value = {"id": self.uid(":response:" + str(len(self.submissions)))}
            self.submissions.append(value)
            return reply(value, 201)
        if path.startswith("submissions/") and path.endswith("/feedback"):
            submission = path.split("/")[1]
            self.polls[path] = self.polls.get(path, 0) + 1
            return reply(
                {
                    "workflow_run_id": self.uid(":workflow:" + submission),
                    "submission_id": submission,
                    "status": "processing" if self.polls[path] == 1 else self.feedback_status,
                    "feedback": {"feedback_id": self.uid(":feedback:" + submission)},
                }
            )
        if path.endswith("/acknowledgement"):
            return reply({})
        if path.startswith("activity-continuation/"):
            return reply(
                {
                    "workflow_id": self.uid(":workflow:" + self.submissions[-1]["id"]),
                    "state": "suggested",
                    "snapshot_id": self.uid(":snapshot"),
                    "version": 0,
                    "rule_version": "approved-activity.v1",
                    "next_task_id": "task38-next",
                }
            )
        if path.endswith("/result"):
            return reply(
                {
                    "assessment_attempt_id": self.uid(":assessment"),
                    "result": "PASS" if self.confirmed else None,
                    "status": "Confirmed by assessor"
                    if self.confirmed
                    else "Awaiting assessor review",
                }
            )
        if path.startswith("students/me/tasks/") and method == "GET":
            return reply(
                {
                    "id": path.split("/")[-1],
                    "task_type": "explanation"
                    if path.endswith("/task38-next")
                    else "quantum_circuit",
                    "assessment": None,
                    "episode_plan": None,
                }
            )
        return reply({}, 404)

    def session(self):
        return httpx.AsyncClient(
            base_url="https://task38.invalid/api/v1/", transport=httpx.MockTransport(self.handle)
        )


def factory(config, budget, samples, result, clock):
    fake = FakeTransport(result["loop_id"])
    return LearningLoop(
        config, budget, samples, result, lambda: fake.now, session=fake.session(), sleep=fake.sleep
    )
