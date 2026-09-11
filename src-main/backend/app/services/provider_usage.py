"""Atomic reservations use independent short transactions, before network I/O.

An ambiguous dispatch never expires or releases money automatically. An operator
can reconcile it using a uniquely identified provider billing record. Estimates
are never treated as actual spend, including when token usage is available.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256

from sqlalchemy import Engine, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.models.provider_usage import ProviderBudget, ProviderUsage


class ProviderBudgetError(RuntimeError):
    """Dispatch is unavailable, exhausted, or already claimed."""


def micros(value: Decimal) -> int:
    if not value.is_finite() or value < 0:
        raise ProviderBudgetError("Invalid monetary amount.")
    result = int((value * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    if result > 9_000_000_000_000_000:
        raise ProviderBudgetError("Monetary amount exceeds supported bounds.")
    return result


@dataclass(frozen=True)
class MeteringPolicy:
    budget_id: str
    currency: str
    policy_version: str
    limit: Decimal
    pricing_version: str
    input_rate: Decimal
    output_rate: Decimal
    max_input_tokens: int
    max_output_tokens: int

    def __post_init__(self):
        if self.limit * 1_000_000 != micros(self.limit):
            raise ProviderBudgetError("Budget amounts support at most six decimal places.")
        if (
            any(
                not value.strip() or len(value) > 120
                for value in (self.budget_id, self.policy_version, self.pricing_version)
            )
            or len(self.currency) != 3
            or not self.currency.isalpha()
            or not self.currency.isupper()
        ):
            raise ProviderBudgetError("Approved budget and pricing provenance are required.")
        for value in (self.limit, self.input_rate, self.output_rate):
            micros(value)
        for value in (self.max_input_tokens, self.max_output_tokens):
            if type(value) is not int or not 1 <= value <= 1_000_000:
                raise ProviderBudgetError("Invalid provider token bound.")

    @property
    def reservation(self) -> int:
        return micros(
            (self.max_input_tokens * self.input_rate + self.max_output_tokens * self.output_rate)
            / 1_000_000
        )


def configured_meter(
    session: Session, *, provider: str, model: str, configured: Settings = settings
) -> "ProviderUsageMeter":
    if configured.llm_budget_limit is None:
        raise ProviderBudgetError("An approved provider budget is required before dispatch.")
    if (
        configured.llm_input_cost_per_million is None
        or configured.llm_output_cost_per_million is None
    ):
        raise ProviderBudgetError("Explicit provider input and output prices are required.")
    if (provider, model, configured.llm_api_base_url) != (
        configured.llm_pricing_provider,
        configured.llm_pricing_model,
        configured.llm_pricing_base_url,
    ):
        raise ProviderBudgetError(
            "Pricing approval does not match the selected provider configuration."
        )
    policy = MeteringPolicy(
        budget_id=configured.llm_budget_id,
        currency=configured.llm_cost_currency,
        policy_version=configured.llm_budget_policy_version,
        limit=configured.llm_budget_limit,
        pricing_version=configured.llm_pricing_version,
        input_rate=configured.llm_input_cost_per_million,
        output_rate=configured.llm_output_cost_per_million,
        max_input_tokens=configured.llm_max_input_tokens,
        max_output_tokens=configured.llm_max_output_tokens,
    )
    bind = session.get_bind()
    if not isinstance(bind, Engine):
        raise ProviderBudgetError("Metering requires independent database transactions.")
    return ProviderUsageMeter(bind, policy)


class ProviderUsageMeter:
    def __init__(self, engine: Engine, policy: MeteringPolicy):
        self.policy = policy
        self._sessions = sessionmaker(engine, expire_on_commit=False)
        self._insert = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ProviderBudgetError("Unsupported budget database.")

    def reserve(self, key: str, payload: dict, provenance: dict) -> None:
        if not key or len(key) > 160:
            raise ProviderBudgetError("Invalid metering key.")
        policy = self.policy
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        # Approved text-only adapter bound: UTF-8 bytes plus framing allowance.
        # Reject oversized inputs before dispatch; output is capped in the request.
        if len(serialized.encode("utf-8")) + 1024 > policy.max_input_tokens:
            raise ProviderBudgetError("Provider input exceeds the approved reservation bound.")
        provenance = {
            **provenance,
            "budget_policy_version": policy.policy_version,
            "pricing_version": policy.pricing_version,
            "currency": policy.currency,
            "input_rate_per_million": str(policy.input_rate),
            "output_rate_per_million": str(policy.output_rate),
            "max_input_tokens": policy.max_input_tokens,
            "max_output_tokens": policy.max_output_tokens,
        }
        fingerprint = sha256(
            json.dumps(
                {"payload": payload, "provenance": provenance}, sort_keys=True, ensure_ascii=False
            ).encode()
        ).hexdigest()
        with self._sessions.begin() as session:
            session.execute(
                self._insert(ProviderBudget)
                .values(
                    id=policy.budget_id,
                    currency=policy.currency,
                    policy_version=policy.policy_version,
                    limit_micros=micros(policy.limit),
                    exposure_micros=0,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            # Write lock on the shared account serializes reserve and reconciliation
            # across processes on SQLite and row-locks on PostgreSQL.
            session.execute(
                update(ProviderBudget)
                .where(ProviderBudget.id == policy.budget_id)
                .values(exposure_micros=ProviderBudget.exposure_micros)
            )
            budget = session.get(ProviderBudget, policy.budget_id)
            if (budget.currency, budget.policy_version, budget.limit_micros) != (
                policy.currency,
                policy.policy_version,
                micros(policy.limit),
            ):
                raise ProviderBudgetError("Budget identity cannot be reused with changed policy.")
            existing = session.get(ProviderUsage, key)
            if existing:
                if (
                    existing.budget_id != policy.budget_id
                    or existing.request_fingerprint != fingerprint
                ):
                    raise ProviderBudgetError("Metering key conflicts with an earlier request.")
                return
            admitted = session.execute(
                update(ProviderBudget)
                .where(
                    ProviderBudget.id == policy.budget_id,
                    ProviderBudget.exposure_micros + policy.reservation
                    <= ProviderBudget.limit_micros,
                )
                .values(exposure_micros=ProviderBudget.exposure_micros + policy.reservation)
            )
            if admitted.rowcount != 1:
                raise ProviderBudgetError("The configured provider budget is exhausted.")
            session.add(
                ProviderUsage(
                    id=key,
                    budget_id=policy.budget_id,
                    request_fingerprint=fingerprint,
                    state="RESERVED",
                    reserved_micros=policy.reservation,
                    exposure_micros=policy.reservation,
                    provenance=provenance,
                )
            )

    def dispatch(self, key: str) -> None:
        with self._sessions.begin() as session:
            claimed = session.execute(
                update(ProviderUsage)
                .where(
                    ProviderUsage.id == key,
                    ProviderUsage.budget_id == self.policy.budget_id,
                    ProviderUsage.state == "RESERVED",
                )
                .values(state="DISPATCHED", updated_at=datetime.now(UTC))
            )
            if claimed.rowcount != 1:
                raise ProviderBudgetError("Provider attempt was already claimed or cancelled.")

    def observe(
        self,
        key: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        response_id: str | None = None,
    ) -> None:
        for value in (input_tokens, output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ProviderBudgetError("Invalid observed provider usage.")
        with self._sessions.begin() as session:
            self._lock_budget(session)
            row = session.get(ProviderUsage, key)
            if row is None or row.budget_id != self.policy.budget_id:
                raise ProviderBudgetError("Unknown provider reservation.")
            if row.state in {"NOT_SENT", "RELEASED"} and all(
                value is None for value in (input_tokens, output_tokens, response_id)
            ):
                # Timeout cleanup can race a completed connection-failure release.
                # Its generic unknown observation cannot reinstate that exposure.
                return
            if row.state not in {"DISPATCHED", "OBSERVED", "UNKNOWN", "RECONCILED"}:
                raise ProviderBudgetError("Usage cannot precede dispatch.")
            for stored, observed in (
                (row.input_tokens, input_tokens),
                (row.output_tokens, output_tokens),
            ):
                if stored is not None and observed is not None and stored != observed:
                    raise ProviderBudgetError("Conflicting observed provider usage.")
            estimate = None
            if input_tokens is not None and output_tokens is not None:
                estimate = micros(
                    (
                        input_tokens * Decimal(row.provenance["input_rate_per_million"])
                        + output_tokens * Decimal(row.provenance["output_rate_per_million"])
                    )
                    / 1_000_000
                )
            if row.estimated_micros is not None:
                if estimate is not None and (row.input_tokens, row.output_tokens) != (
                    input_tokens,
                    output_tokens,
                ):
                    raise ProviderBudgetError("Conflicting observed provider usage.")
                return
            if input_tokens is not None:
                row.input_tokens = input_tokens
            if output_tokens is not None:
                row.output_tokens = output_tokens
            row.estimated_micros = estimate
            if response_id is not None:
                row.provider_response_id = response_id
            row.updated_at = datetime.now(UTC)
            if row.state != "RECONCILED":
                row.state = "OBSERVED" if estimate is not None else "UNKNOWN"
                # A provider violating its configured bound must not silently
                # undercount known exposure. Preserve the original reservation.
                if estimate is not None and estimate > row.exposure_micros:
                    session.execute(
                        update(ProviderBudget)
                        .where(ProviderBudget.id == row.budget_id)
                        .values(
                            exposure_micros=ProviderBudget.exposure_micros
                            + estimate
                            - row.exposure_micros
                        )
                    )
                    row.exposure_micros = estimate

    def release_undispatched(self, key: str) -> None:
        """Recover an orphan reservation; dispatch and release race through a CAS."""
        with self._sessions.begin() as session:
            self._lock_budget(session)
            row = session.get(ProviderUsage, key)
            if row is None or row.budget_id != self.policy.budget_id:
                raise ProviderBudgetError("Unknown provider reservation.")
            result = session.execute(
                update(ProviderUsage)
                .where(ProviderUsage.id == key, ProviderUsage.state == "RESERVED")
                .values(state="RELEASED", exposure_micros=0, updated_at=datetime.now(UTC))
            )
            if result.rowcount:
                session.execute(
                    update(ProviderBudget)
                    .where(ProviderBudget.id == row.budget_id)
                    .values(exposure_micros=ProviderBudget.exposure_micros - row.reserved_micros)
                )
            elif row.state != "RELEASED":
                raise ProviderBudgetError("A dispatched reservation requires billing evidence.")

    def connection_failed(self, key: str) -> None:
        """Transport attests a connect failure before any request was dispatched."""
        with self._sessions.begin() as session:
            self._lock_budget(session)
            row = session.get(ProviderUsage, key)
            if row is None or row.budget_id != self.policy.budget_id:
                raise ProviderBudgetError("Unknown provider reservation.")
            result = session.execute(
                update(ProviderUsage)
                .where(ProviderUsage.id == key, ProviderUsage.state == "DISPATCHED")
                .values(state="NOT_SENT", exposure_micros=0, updated_at=datetime.now(UTC))
            )
            if result.rowcount:
                session.execute(
                    update(ProviderBudget)
                    .where(ProviderBudget.id == row.budget_id)
                    .values(exposure_micros=ProviderBudget.exposure_micros - row.reserved_micros)
                )

    def _lock_budget(self, session: Session) -> None:
        session.execute(
            update(ProviderBudget)
            .where(ProviderBudget.id == self.policy.budget_id)
            .values(exposure_micros=ProviderBudget.exposure_micros)
        )

    def reconcile(
        self, key: str, *, actual: Decimal, currency: str, receipt_id: str, actor: str
    ) -> None:
        """Apply an attributable billing receipt once, retaining over-budget actuals."""
        amount = micros(actual)
        if actual * 1_000_000 != amount or not actor.strip() or len(actor) > 120:
            raise ProviderBudgetError(
                "Exact monetary precision and a recording actor are required."
            )
        if currency != self.policy.currency or not receipt_id.strip() or len(receipt_id) > 200:
            raise ProviderBudgetError("Matching currency and billing evidence are required.")
        with self._sessions.begin() as session:
            self._lock_budget(session)
            row = session.get(ProviderUsage, key)
            if row is None or row.budget_id != self.policy.budget_id:
                raise ProviderBudgetError("Unknown provider reservation.")
            if row.state == "RECONCILED":
                if row.actual_micros != amount or row.receipt_id != receipt_id:
                    raise ProviderBudgetError("Conflicting billing reconciliation.")
                return
            if row.state not in {"DISPATCHED", "OBSERVED", "UNKNOWN"}:
                raise ProviderBudgetError("Only dispatched usage can be reconciled.")
            row.actual_micros, row.receipt_id, row.state = amount, receipt_id, "RECONCILED"
            row.reconciliation_actor, row.reconciled_at = actor, datetime.now(UTC)
            row.updated_at = datetime.now(UTC)
            session.execute(
                update(ProviderBudget)
                .where(ProviderBudget.id == row.budget_id)
                .values(
                    exposure_micros=ProviderBudget.exposure_micros - row.exposure_micros + amount
                )
            )
            row.exposure_micros = amount
