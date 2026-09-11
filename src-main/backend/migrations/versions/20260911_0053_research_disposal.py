"""Permit exact audited restricted-text disposal, preserving all other history guards."""

from alembic import op

revision = "20260911_0053"
down_revision = "20260911_0052"
branch_labels = None
depends_on = None

DELETE_GUARD = """CREATE TRIGGER restricted_instrument_evidence_no_delete
BEFORE DELETE ON restricted_instrument_evidence
WHEN NOT EXISTS (
 SELECT 1 FROM research_governance_events AS event,
 json_each(event.command, '$.decision.records') AS item
 WHERE event.kind = 'disposal_execution'
 AND json_extract(item.value, '$.evidence_id') = OLD.id
 AND json_extract(item.value, '$.record_id') = OLD.record_id
 AND json_extract(item.value, '$.content_digest') = OLD.content_digest
)
BEGIN SELECT RAISE(ABORT, 'restricted_instrument_evidence history is immutable'); END"""


def upgrade():
    op.execute("DROP TRIGGER IF EXISTS restricted_instrument_evidence_no_delete")
    op.execute(DELETE_GUARD)


def downgrade():
    # Reinstates stricter protection; deleted content is not reconstructed.
    op.execute("DROP TRIGGER IF EXISTS restricted_instrument_evidence_no_delete")
    op.execute(
        "CREATE TRIGGER restricted_instrument_evidence_no_delete BEFORE DELETE ON restricted_instrument_evidence BEGIN SELECT RAISE(ABORT, 'restricted_instrument_evidence history is immutable'); END"
    )
