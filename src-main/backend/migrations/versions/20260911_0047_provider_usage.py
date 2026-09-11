"""Durable provider budgets and usage; no approved amounts or historical backfill."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0047"
down_revision = "20260910_0046"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE TABLE provider_budgets (\n\tid VARCHAR(120) NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tpolicy_version VARCHAR(120) NOT NULL, \n\tlimit_micros BIGINT NOT NULL, \n\texposure_micros BIGINT NOT NULL, \n\tCONSTRAINT pk_provider_budgets PRIMARY KEY (id), \n\tCONSTRAINT ck_provider_budgets_budget_nonnegative CHECK (limit_micros >= 0 AND exposure_micros >= 0)\n)",
    "CREATE TABLE provider_usage (\n\tid VARCHAR(160) NOT NULL, \n\tbudget_id VARCHAR(120) NOT NULL, \n\trequest_fingerprint VARCHAR(64) NOT NULL, \n\tstate VARCHAR(24) NOT NULL, \n\treserved_micros BIGINT NOT NULL, \n\texposure_micros BIGINT NOT NULL, \n\testimated_micros BIGINT, \n\tactual_micros BIGINT, \n\tinput_tokens BIGINT, \n\toutput_tokens BIGINT, \n\tprovider_response_id VARCHAR(200), \n\treceipt_id VARCHAR(200), \n\treconciliation_actor VARCHAR(120), \n\treconciled_at DATETIME, \n\tprovenance JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tupdated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_provider_usage PRIMARY KEY (id), \n\tCONSTRAINT ck_provider_usage_usage_reservation_nonnegative CHECK (reserved_micros >= 0), \n\tCONSTRAINT ck_provider_usage_usage_exposure_nonnegative CHECK (exposure_micros >= 0), \n\tCONSTRAINT ck_provider_usage_usage_actual_nonnegative CHECK (actual_micros IS NULL OR actual_micros >= 0), \n\tCONSTRAINT ck_provider_usage_usage_state CHECK (state IN ('RESERVED','DISPATCHED','OBSERVED','UNKNOWN','RELEASED','NOT_SENT','RECONCILED')), \n\tCONSTRAINT fk_provider_usage_budget_id_provider_budgets FOREIGN KEY(budget_id) REFERENCES provider_budgets (id), \n\tCONSTRAINT uq_provider_usage_receipt_id UNIQUE (receipt_id)\n)",
    "CREATE INDEX ix_provider_usage_budget_id ON provider_usage (budget_id)",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT COUNT(*) FROM provider_budgets")).scalar():
        raise RuntimeError(
            "Retain provider metering history; restore a verified backup for rollback."
        )
    op.drop_table("provider_usage")
    op.drop_table("provider_budgets")
