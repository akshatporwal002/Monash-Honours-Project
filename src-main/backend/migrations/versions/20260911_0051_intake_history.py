"""Preserve course metadata and quarantine material pending malware scanning."""

from alembic import context, op
from sqlalchemy import inspect

revision = "20260911_0051"
down_revision = "20260910_0046"
branch_labels = None
depends_on = None

_STATEMENTS = (
    "\nCREATE TABLE IF NOT EXISTS course_revisions (\n\tid VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tmetadata_snapshot JSON NOT NULL, \n\tcontext_snapshot JSON NOT NULL, \n\tactor_id VARCHAR(255), \n\taction VARCHAR(32) NOT NULL, \n\treason TEXT NOT NULL, \n\trestored_from_id VARCHAR(36), \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_course_revisions PRIMARY KEY (id), \n\tCONSTRAINT uq_course_revisions_course_id UNIQUE (course_id, version), \n\tCONSTRAINT fk_course_revisions_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_course_revisions_restored_from_id_course_revisions FOREIGN KEY(restored_from_id) REFERENCES course_revisions (id)\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS course_revisions_no_update BEFORE UPDATE ON course_revisions BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS course_revisions_no_delete BEFORE DELETE ON course_revisions BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS course_revisions_no_insert BEFORE INSERT ON course_revisions WHEN EXISTS (SELECT 1 FROM course_revisions WHERE id=NEW.id OR (course_id=NEW.course_id AND version=NEW.version)) BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "\nCREATE TABLE IF NOT EXISTS material_scans (\n\tid VARCHAR(36) NOT NULL, \n\tmaterial_id VARCHAR(36) NOT NULL, \n\tcontent_hash VARCHAR(128) NOT NULL, \n\tprocessing_revision INTEGER NOT NULL, \n\tclaim_token VARCHAR(36) NOT NULL, \n\tpolicy_version VARCHAR(255) NOT NULL, \n\tscanner VARCHAR(255) NOT NULL, \n\tscanner_version VARCHAR(255) NOT NULL, \n\tstatus VARCHAR(24) NOT NULL, \n\tcode VARCHAR(100) NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_material_scans PRIMARY KEY (id), \n\tCONSTRAINT fk_material_scans_material_id_learning_materials FOREIGN KEY(material_id) REFERENCES learning_materials (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS material_scans_no_update BEFORE UPDATE ON material_scans BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS material_scans_no_delete BEFORE DELETE ON material_scans BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS material_scans_no_insert BEFORE INSERT ON material_scans WHEN EXISTS (SELECT 1 FROM material_scans WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END",
    "ALTER TABLE learning_materials ADD COLUMN scan_status VARCHAR(24) NOT NULL DEFAULT 'QUARANTINED'",
    "ALTER TABLE learning_materials ADD COLUMN current_scan_id VARCHAR(36)",
    "INSERT INTO course_revisions (id,course_id,version,metadata_snapshot,context_snapshot,actor_id,action,reason,created_at)\nSELECT lower(hex(randomblob(16))),c.id,1,\njson_object('code',c.code,'title',c.title,'description',c.description,'state',c.state,'enrollment_open',json(CASE WHEN c.enrollment_open THEN 'true' ELSE 'false' END),'time_zone',c.time_zone),\njson_object('modules',json((SELECT json_group_array(json_object('id',m.id,'title',m.title,'description',m.description,'position',m.position)) FROM course_modules m WHERE m.course_id=c.id)),\n'enrollments',json((SELECT json_group_array(json_object('id',e.id,'student_id',e.student_id,'status',e.status)) FROM enrollments e WHERE e.course_id=c.id)),\n'sources',json((SELECT json_group_array(json_object('material_id',m.id,'revision_id',m.current_source_revision_id,'content_hash',m.content_hash,'retired',json(CASE WHEN m.retired_at IS NULL THEN 'false' ELSE 'true' END))) FROM learning_materials m WHERE m.course_id=c.id))),\nNULL,'LEGACY_SNAPSHOT','State at migration; original change actor and time unknown',CURRENT_TIMESTAMP FROM courses c WHERE NOT EXISTS (SELECT 1 FROM course_revisions r WHERE r.course_id=c.id)",
)


def upgrade():
    existing_columns = set() if context.is_offline_mode() else {
        column["name"] for column in inspect(op.get_bind()).get_columns("learning_materials")
    }
    for statement in _STATEMENTS:
        if statement.startswith("ALTER TABLE") and statement.split()[5] in existing_columns:
            continue
        op.execute(statement)


def downgrade():
    raise RuntimeError("Intake history is protected; restore a verified backup instead")
