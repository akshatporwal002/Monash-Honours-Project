"""Operator-only usage inspection and evidence-backed reconciliation.

Run with the backend environment and database access of an authorised operator.
This tool never calls a provider or automatically expires an ambiguous charge.
"""

import argparse
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.provider_usage import ProviderBudget, ProviderUsage
from app.services.provider_usage import MeteringPolicy, ProviderBudgetError, ProviderUsageMeter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--budget-id", required=True)
    listing.add_argument("--limit", type=int, default=100)
    for name in ("release-undispatched", "reconcile"):
        action = actions.add_parser(name)
        action.add_argument("--usage-id", required=True)
        if name == "reconcile":
            action.add_argument("--actual", type=Decimal, required=True)
            action.add_argument("--currency", required=True)
            action.add_argument("--receipt-id", required=True)
            action.add_argument("--actor", required=True)
    args = parser.parse_args()
    with Session(engine) as session:
        if args.action == "list":
            if not 1 <= args.limit <= 1000:
                parser.error("limit must be between 1 and 1000")
            rows = session.scalars(
                select(ProviderUsage)
                .where(ProviderUsage.budget_id == args.budget_id)
                .order_by(ProviderUsage.created_at, ProviderUsage.id)
                .limit(args.limit)
            ).all()
            print(
                json.dumps(
                    [
                        {
                            column.name: getattr(row, column.name)
                            for column in ProviderUsage.__table__.columns
                        }
                        for row in rows
                    ],
                    default=str,
                    indent=2,
                )
            )
            return
        row = session.get(ProviderUsage, args.usage_id)
        if row is None:
            parser.error("unknown usage ID")
        budget = session.get(ProviderBudget, row.budget_id)
        # Recovery binds the original recorded policy, even after deployment
        # settings have changed. It cannot create new spend or dispatch calls.
        provenance = row.provenance
        policy = MeteringPolicy(
            budget.id,
            budget.currency,
            budget.policy_version,
            Decimal(budget.limit_micros) / 1_000_000,
            provenance["pricing_version"],
            Decimal(provenance["input_rate_per_million"]),
            Decimal(provenance["output_rate_per_million"]),
            provenance["max_input_tokens"],
            provenance["max_output_tokens"],
        )
    meter = ProviderUsageMeter(engine, policy)
    try:
        if args.action == "release-undispatched":
            meter.release_undispatched(args.usage_id)
        else:
            meter.reconcile(
                args.usage_id,
                actual=args.actual,
                currency=args.currency,
                receipt_id=args.receipt_id,
                actor=args.actor,
            )
    except ProviderBudgetError as error:
        parser.error(str(error))
    print("Provider usage record updated.")


if __name__ == "__main__":
    main()
