"""Retain exact authenticated category quality reviews without rewriting approvals."""

from alembic import op

revision = "20260911_0054"
down_revision = "20260911_0053"
branch_labels = None
depends_on = None

_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS category_quality_reviews (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        course_id VARCHAR(36) NOT NULL,
        task_revision_id VARCHAR(36) NOT NULL,
        task_review_event_id VARCHAR(36) NOT NULL,
        reviewer_id INTEGER NOT NULL,
        request_digest VARCHAR(64) NOT NULL CHECK(length(request_digest)=64),
        decision VARCHAR(16) NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
        receipt JSON NOT NULL,
        created_at DATETIME NOT NULL,
        CONSTRAINT uq_category_quality_event UNIQUE(task_review_event_id),
        CONSTRAINT fk_category_quality_reviews_task_review_event_id_task_review_events FOREIGN KEY(task_review_event_id) REFERENCES task_review_events(id) ON DELETE RESTRICT,
        CONSTRAINT fk_category_quality_reviews_reviewer_id_users FOREIGN KEY(reviewer_id) REFERENCES users(id) ON DELETE RESTRICT,
        FOREIGN KEY(task_revision_id,course_id) REFERENCES task_revisions(id,course_id) ON DELETE RESTRICT
    )""",
    "CREATE TRIGGER IF NOT EXISTS category_quality_reviews_no_update BEFORE UPDATE ON category_quality_reviews BEGIN SELECT RAISE(ABORT, 'Category review history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS category_quality_reviews_no_delete BEFORE DELETE ON category_quality_reviews BEGIN SELECT RAISE(ABORT, 'Category review history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS category_quality_reviews_no_replace BEFORE INSERT ON category_quality_reviews WHEN EXISTS (SELECT 1 FROM category_quality_reviews WHERE id=NEW.id OR task_review_event_id=NEW.task_review_event_id) BEGIN SELECT RAISE(ABORT, 'Category review history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS category_quality_reviews_scope BEFORE INSERT ON category_quality_reviews WHEN NOT EXISTS (SELECT 1 FROM task_review_events e WHERE e.id=NEW.task_review_event_id AND e.course_id=NEW.course_id AND e.task_revision_id=NEW.task_revision_id AND e.actor_user_id=NEW.reviewer_id AND e.state IN ('APPROVED','REJECTED') AND (e.state='REJECTED' OR NEW.decision='APPROVED')) BEGIN SELECT RAISE(ABORT, 'Category review event scope differs'); END",
)


def upgrade():
    for statement in _STATEMENTS:
        op.execute(statement)


def downgrade():
    raise RuntimeError("Category review history is protected; restore a verified backup instead")
