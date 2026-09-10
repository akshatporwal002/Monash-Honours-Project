"""The shipped cookie/CSRF API, without internal routes or automated assessor actions."""

from __future__ import annotations

import asyncio
import copy
from contextlib import asynccontextmanager

import httpx

from .core import StopRun


class LearningLoop:
    def __init__(self, config, budget, samples, result, clock, session=None, sleep=asyncio.sleep):
        self.config, self.budget, self.samples, self.result = config, budget, samples, result
        self.clock, self.sleep = clock, sleep
        self.session = session or httpx.AsyncClient(
            base_url=config.target.rstrip("/") + "/",
            timeout=config.request_timeout,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=1),
        )

    async def close(self):
        await self.session.aclose()

    @asynccontextmanager
    async def measure(self, category, kind="operation", route=None):
        start, ok, censored = self.clock(), False, False
        reason = None
        try:
            yield
            ok = True
        except (asyncio.CancelledError, TimeoutError, httpx.TimeoutException):
            censored, reason = True, "deadline_or_cancelled"
            raise
        except StopRun as error:
            reason = str(error)
            censored = reason.endswith("timeout") or reason.endswith("budget")
            raise
        except Exception:
            reason = "transport_or_contract_error"
            raise
        finally:
            self.samples.append(
                {
                    "loop_id": self.result["loop_id"],
                    "users": self.result["users"],
                    "phase": self.result["phase"],
                    "category": category,
                    "kind": kind,
                    "route": route,
                    "seconds": self.clock() - start,
                    "ok": ok,
                    "censored": censored,
                    "error": reason,
                }
            )

    async def request(
        self, method, path, body=None, category="control", expected=(200,), label=None
    ):
        self.budget.request()
        async with self.measure(category, "http", label or path.split("?")[0]):
            headers = {"Origin": self.config.origin, "X-Correlation-ID": self.correlation_id()}
            csrf = self.session.cookies.get(self.config.csrf_cookie)
            if csrf:
                headers[self.config.csrf_header] = csrf
            try:
                async with asyncio.timeout(self.config.request_timeout):
                    response = await self.session.request(
                        method, path.lstrip("/"), json=body, headers=headers
                    )
            except httpx.TimeoutException:
                raise StopRun("request_timeout") from None
            except httpx.HTTPError:
                raise StopRun("transport_error") from None
            if response.status_code not in expected:
                raise StopRun(f"http_{response.status_code}")
            return response.json() if response.content else None

    def correlation_id(self):
        from uuid import NAMESPACE_URL, uuid5

        return str(uuid5(NAMESPACE_URL, f"{self.result['loop_id']}:{self.budget.requests}"))

    async def poll(self, path, predicate, timeout, category):
        deadline = self.clock() + timeout
        # Wall timeout also bounds a final HTTP request crossing the deadline.
        try:
            async with asyncio.timeout(timeout):
                while self.clock() < deadline:
                    value = await self.request("GET", path, category="poll")
                    if predicate(value):
                        return value
                    await self.sleep(min(self.config.poll_seconds, max(0, deadline - self.clock())))
        except TimeoutError:
            raise StopRun(f"{category}_timeout") from None
        raise StopRun(f"{category}_timeout")

    async def run(self, fixture):
        c, r = self.config, self.result
        actor = await self.request(
            "POST",
            "auth/login",
            {"email": fixture["student_email"], "password": fixture["student_password"]},
        )
        if actor.get("role") != "student" or actor["id"] in self.budget.actor_ids:
            raise StopRun("fixture_actor_not_unique_student")
        self.budget.actor_ids.add(actor["id"])
        task = f"students/me/tasks/{fixture['task_id']}"
        await self.request("GET", "students/me/dashboard", category="ordinary")
        await self.request("GET", task, category="ordinary")
        # Refuse reused assessment state, including a previous campaign's learner.
        if await self.request("GET", task + "/draft", category="ordinary") is not None:
            raise StopRun("fixture_already_started")
        if await self.request("GET", task + "/submissions", category="ordinary"):
            raise StopRun("fixture_already_submitted")
        await self.request("GET", f"progress/{fixture['course_id']}", category="progress")
        started = await self.request(
            "POST", task + "/start", {"task_form_version_id": fixture["form_id"]}
        )
        payload = copy.deepcopy(fixture["response"])
        payload["assessment_work_start_id"] = started["assessment_work_start_id"]
        # A representative approved conceptual hint, not an instructional allowance/cap.
        await self.request(
            "POST",
            task + "/episode/help",
            {
                "assessment_work_start_id": payload["assessment_work_start_id"],
                "kind": "conceptual_hint",
                "item_index": 0,
                "request_key": r["loop_id"] + ":hint",
            },
        )
        payload = await self.simulate(task, fixture, payload)
        state = await self.request("POST", task + "/episode/transfer", payload)
        transfer = copy.deepcopy(fixture["transfer"])
        transfer.update(
            stage_start_id=state["transfer"]["stage_start_id"], part_id=state["transfer"]["part_id"]
        )
        payload["episode"]["transfer"] = transfer
        # No tutor or conceptual help requests after entering unaided transfer.
        payload = await self.simulate(task, fixture, payload, transfer=True)
        await self.request("PUT", task + "/draft", payload)
        await self.request("GET", task + "/draft", category="ordinary")
        for attempt in range(2):
            if attempt:
                payload["episode"]["supported"]["revision"] = {
                    "previous_response_version_id": r["submission_ids"][0],
                    "reason": "Synthetic learner reviewed the checked feedback.",
                }
                payload["episode"]["supported"]["reflection"] = fixture["revision_reflection"]
            submission_id = await self.submit_and_wait(
                task, payload, str(attempt), "assessed_feedback"
            )
            async with self.measure("continuation"):
                activity = await self.poll(
                    f"activity-continuation/submissions/{submission_id}",
                    lambda v: v is not None and v["state"] != "processing",
                    c.worker_timeout,
                    "continuation",
                )
                if activity["state"] != "suggested" or not activity["snapshot_id"]:
                    raise StopRun("continuation_unavailable")
                r["activity_rule_version"] = activity["rule_version"]
        chosen = await self.request(
            "POST",
            f"activity-continuation/{activity['workflow_id']}/actions",
            {
                "expected_version": activity["version"],
                "request_key": r["loop_id"] + ":choice",
                "action": "accept",
            },
        )
        if not chosen["next_task_id"]:
            raise StopRun("choice_unavailable")
        await self.request(
            "GET", f"students/me/tasks/{chosen['next_task_id']}", category="ordinary"
        )
        # Assessed feedback deliberately bypasses external LLMs in the shipped service.
        # The approved formative next activity exercises the real configurable provider path.
        await self.submit_and_wait(
            f"students/me/tasks/{chosen['next_task_id']}",
            {"answer": fixture["next_activity_answer"]},
            "next",
            "feedback",
        )
        await self.request("GET", f"progress/{fixture['course_id']}", category="progress")
        r["learning_complete"] = True
        path = f"students/me/responses/{submission_id}/result"
        formal = await self.request("GET", path)
        r["assessment_attempt_id"] = formal["assessment_attempt_id"]

        def confirmed(value):
            return value["result"] in {"PASS", "INCOMPLETE"} and value["status"] in {
                "Confirmed by assessor",
                "Updated by assessor",
            }

        if not confirmed(formal) and c.human_timeout:
            async with self.measure("human_confirmation"):
                formal = await self.poll(path, confirmed, c.human_timeout, "human")
        r["status"] = "complete" if confirmed(formal) else "awaiting_human"
        r["formal_result"] = formal["result"] if confirmed(formal) else None

    async def submit_and_wait(self, task, payload, key, category):
        r = self.result
        async with self.measure(category):
            submitted = await self.request(
                "POST",
                task + "/submissions",
                {**payload, "idempotency_key": r["loop_id"] + ":submit:" + key},
                expected=(201,),
            )
            submission_id = submitted["id"]
            r["submission_ids"].append(submission_id)
            feedback_path = f"submissions/{submission_id}/feedback"

            def terminal(value):
                identity = value["workflow_run_id"]
                if identity not in r["workflow_ids"]:
                    r["workflow_ids"].append(identity)
                r.setdefault("feedback_states", []).append(
                    {
                        "workflow_id": identity,
                        "status": value["status"],
                        "processing_stage": value.get("processing_stage"),
                        "category": category,
                    }
                )
                return value["status"] in {"validated", "fallback", "failed"}

            feedback = await self.poll(
                feedback_path, terminal, self.config.worker_timeout, "feedback"
            )
            if feedback["status"] != "validated":
                raise StopRun("feedback_" + feedback["status"])
        await self.request(
            "POST",
            feedback_path + "/acknowledgement",
            {"feedback_id": feedback["feedback"]["feedback_id"]},
        )
        return submission_id

    async def simulate(self, task, fixture, payload, transfer=False):
        stage = payload["episode"]["transfer"] if transfer else None
        part_id = stage["part_id"] if stage else "supported"
        stage_id = stage["stage_start_id"] if stage else None
        saved = await self.request(
            "POST",
            task + "/episode/checkpoints",
            {"response": payload, "part_id": part_id, "stage_start_id": stage_id},
        )
        payload = {
            k: v for k, v in saved["draft"].items() if k not in {"id", "task_id", "updated_at"}
        }
        simulation = await self.request(
            "POST",
            "students/me/simulate",
            {
                "task_id": fixture["task_id"],
                **(stage["content"]["circuit"] if stage else payload["circuit"]),
                "shots": 1024,
                "seed": 42,
                "prediction_checkpoint_id": saved["checkpoint_id"],
                "episode_stage_start_id": stage_id,
                "episode_part_id": part_id,
                "request_key": self.result["loop_id"] + ":simulation:" + part_id,
            },
            category="simulation",
        )
        if simulation["status"] != "completed":
            raise StopRun("simulation_" + simulation["status"])
        target = (
            payload["episode"]["transfer"]["process"]
            if transfer
            else payload["episode"]["supported"]
        )
        target["simulation_references"] = [
            {"run_id": simulation["run_id"], "circuit_version_id": simulation["circuit_version_id"]}
        ]
        return payload


async def probe_settings(admin: LearningLoop, learner: LearningLoop, desired):
    """Run separately before load; restore original supported values even on failure."""
    results = {
        key: {"status": "missing_runtime_interface"} for key in ("timeout", "retry", "budget")
    }
    original = await admin.request("GET", "admin/settings")
    restore = {key: original[key] for key in ("llm_provider", "llm_model")}
    admin.result["settings_original"] = restore
    if any(desired[key] == value for key, value in restore.items()):
        raise StopRun("settings_probe_requires_different_values")
    try:
        for key in restore:
            await learner.request("PUT", "admin/settings", {key: desired[key]}, expected=(403,))
            after_denial = await admin.request("GET", "admin/settings")
            if after_denial[key] != original[key]:
                raise StopRun("unauthorized_settings_changed")
            changed = await admin.request("PUT", "admin/settings", {key: desired[key]})
            observed = await admin.request("GET", "admin/settings")
            if changed[key] != desired[key] or observed[key] != desired[key]:
                raise StopRun("settings_not_applied")
            results[key] = {
                "original": original[key],
                "requested": desired[key],
                "observed": observed[key],
                "authorized": "applied_and_read_back",
                "unauthorized": "denied_403",
                "runtime_effect": "pending usage receipt from later workflow",
            }
    finally:
        # Restoration has its own reserved request allowance, even on cancellation/budget exhaustion.
        saved_limit, stopped = admin.budget.config.max_requests, admin.budget.stopped
        from dataclasses import replace

        admin.budget.config = replace(admin.budget.config, max_requests=admin.budget.requests + 2)
        admin.budget.stopped = False
        try:
            await admin.request("PUT", "admin/settings", restore)
            restored = await admin.request("GET", "admin/settings")
            if any(restored[k] != v for k, v in restore.items()):
                raise StopRun("settings_restore_failed")
            results["restored"] = True
        finally:
            admin.budget.config = replace(admin.budget.config, max_requests=saved_limit)
            admin.budget.stopped = stopped
    return results
