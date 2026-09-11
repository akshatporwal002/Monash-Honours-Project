"""Only an exact immutable execution receipt authorizes restricted-text deletion."""

DISPOSAL_DELETE_AUTHORIZATION = """EXISTS (
 SELECT 1 FROM research_governance_events AS event,
 json_each(event.command, '$.decision.records') AS item
 WHERE event.kind = 'disposal_execution'
 AND json_extract(item.value, '$.evidence_id') = OLD.id
 AND json_extract(item.value, '$.record_id') = OLD.record_id
 AND json_extract(item.value, '$.content_digest') = OLD.content_digest
)"""
