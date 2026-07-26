#!/bin/sh
set -eu

umask 027

case "${MIGRATE_ON_START:-true}" in
    true)
        alembic upgrade head
        ;;
    false)
        ;;
    *)
        echo "MIGRATE_ON_START must be true or false." >&2
        exit 2
        ;;
esac

case "${BOOTSTRAP_DEMO:-false}" in
    true)
        python - <<'PY'
from app.db.session import SessionLocal
from app.services.lms import bootstrap_demo

with SessionLocal() as session:
    bootstrap_demo(session)
PY
        ;;
    false)
        ;;
    *)
        echo "BOOTSTRAP_DEMO must be true or false." >&2
        exit 2
        ;;
esac

exec "$@"
