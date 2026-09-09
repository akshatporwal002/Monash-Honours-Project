"""Both shipped preference interfaces share one protected history."""

from sqlalchemy import select
from test_learner_preferences import command, learner

from app.models.learner_preferences import LearnerPreferenceRevision
from app.services.learner_preferences import LearnerPreferenceService
from app.services.learner_preferences.contracts import LearnerPreferencesWrite
from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
from app.services.learner_preferences.service import LearnerPreferencesService


def test_both_interfaces_share_opt_out_and_preserve_support(db_session):
    actor = learner(db_session)
    support = LearnerPreferenceService(db_session)
    published = LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(db_session))
    support.save(actor, command(support_amount="on_request", feedback_form="expandable"))
    assert published.read(actor.id).revision == 1
    published.save(
        actor.id,
        LearnerPreferencesWrite(
            pace="FASTER",
            format="VISUAL",
            explanation_detail="STANDARD",
            optional_breaks_enabled=True,
            repeat_practice_enabled=False,
            personalisation_enabled=False,
            expected_revision=1,
            idempotency_key="published-opt-out",
        ),
    )
    assert not support.read(actor).values.personalisation_enabled
    assert support.read(actor).values.support_amount == "on_request"
    assert support.read(actor).values.feedback_form == "expandable"
    support.save(actor, command(2, "support-opt-in", personalisation_enabled=True))
    assert published.read(actor.id).personalisation_enabled
    rows = list(
        db_session.scalars(
            select(LearnerPreferenceRevision).order_by(LearnerPreferenceRevision.revision)
        )
    )
    assert [row.revision for row in rows] == [1, 2, 3]
    assert rows[1].prior_revision_id == rows[0].id
    assert rows[2].prior_revision_id == rows[1].id


def test_published_preference_rows_survive_forward_upgrade(tmp_path):
    from alembic import command as migration
    from sqlalchemy import create_engine, text
    from test_migrations import migration_config

    url = f"sqlite:///{(tmp_path / 'published.db').as_posix()}"
    config = migration_config(url)
    migration.upgrade(config, "20260909_0039")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,full_name,password_hash,role,is_active,created_at,updated_at) VALUES (991,'published@example.test','Published learner','unused','student',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO learner_preference_revisions (id,learner_id,revision,pace,format,explanation_detail,optional_breaks_enabled,repeat_practice_enabled,personalisation_enabled,schema_version,actor_reference,correlation_id,idempotency_key,occurred_at,created_at) VALUES ('published-revision',991,1,'FASTER','VISUAL','STANDARD',1,0,0,'learnlens.learner-preferences.v1','991','published-correlation','published-key',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        before = dict(
            connection.execute(text("SELECT * FROM learner_preference_revisions")).mappings().one()
        )
    migration.upgrade(config, "head")
    migration.check(config)
    with engine.connect() as connection:
        after = dict(
            connection.execute(text("SELECT * FROM learner_preference_revisions")).mappings().one()
        )
        assert all(after[key] == value for key, value in before.items())
        assert after["support_amount"] == "standard"
        assert after["feedback_form"] == "inline"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
