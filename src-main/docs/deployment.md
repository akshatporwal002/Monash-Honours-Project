# QuantumLearn deployment

This package runs the React application and FastAPI service behind one nginx
origin. The API is not published directly. SQLite and uploaded learning
materials live together in the `quantumlearn_data` Docker volume.

## Local Docker deployment

Requirements:

- Docker Engine with Docker Compose v2
- Python 3.11 or newer only if running the host-side smoke check

From `src-main`:

```sh
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
python scripts/smoke_check.py --base-url http://localhost:8080
```

The local example explicitly enables demo bootstrap. Its accounts use password
`quantumlearn-demo`:

- `student@quantumlearn.demo`
- `educator@quantumlearn.demo`
- `admin@quantumlearn.demo`

Do not use those accounts or the placeholder secrets in a hosted environment.

Stop the containers without deleting data:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml down
```

Deleting the `quantumlearn_data` volume permanently removes the SQLite database
and uploaded course material. Back up that volume before upgrades and never use
`down --volumes` unless data deletion is intentional.

## Hosted Ubuntu Docker deployment

The supported reference environment is one Ubuntu 24.04 LTS virtual machine
running Docker Engine and the Docker Compose plugin. The Compose port remains
bound to `127.0.0.1`; a host-managed HTTPS reverse proxy terminates TLS and
forwards the public origin to `http://127.0.0.1:8080`.

1. Point the public DNS name at the VM and configure its TLS certificate in the
   host reverse proxy.
2. Copy `deploy/.env.example` to `deploy/.env` and restrict it to the deployment
   user.
3. Set `PUBLIC_ORIGIN` to the exact HTTPS origin, without a trailing slash.
4. Generate two independent random values of at least 32 bytes for
   `SESSION_SECRET_KEY` and `LEARNING_EVENT_PSEUDONYM_SECRET`.
5. Keep `BIND_ADDRESS=127.0.0.1`. Set a non-placeholder `IMAGE_TAG` for each
   release.
6. Validate and start the production overlay:

```sh
docker compose \
  --env-file deploy/.env \
  -f deploy/compose.yaml \
  -f deploy/compose.hosted.yaml \
  config --quiet

docker compose \
  --env-file deploy/.env \
  -f deploy/compose.yaml \
  -f deploy/compose.hosted.yaml \
  up --build -d

QUANTUMLEARN_BASE_URL=https://learn.example.edu \
  python3 scripts/smoke_check.py
```

After the first hosted start, provision the sole initial administrator from an
interactive terminal:

```sh
docker compose \
  --env-file deploy/.env \
  -f deploy/compose.yaml \
  -f deploy/compose.hosted.yaml \
  exec backend quantumlearn-provision-admin
```

The command accepts no arguments, reads the password twice from hidden prompts,
stores only an Argon2id hash, and atomically writes a correlated platform audit
record. It refuses to create another account after an administrator exists.
Never put the password in a command argument, environment variable, shell
history, or redirected input.

The host TLS proxy must preserve `Host`, set `X-Forwarded-Proto` to `https`,
and replace rather than trust client-supplied forwarding headers. Only ports 80
and 443 should be publicly reachable; the Compose port and Docker network stay
private.

The hosted overlay forces:

- `APP_ENV=production`
- secure session and CSRF cookies
- interactive API documentation off
- demo bootstrap off
- frontend and CORS origins to `PUBLIC_ORIGIN`

## Operations and limits

The backend entrypoint applies `alembic upgrade head` before it accepts traffic.
Run one backend replica: SQLite supports this MVP deployment but is not a
multi-replica database. The containers run without root privileges, drop Linux
capabilities, use read-only root filesystems, and rotate Docker JSON logs.

`GET /api/v1/health` is the liveness check used by Docker. `GET /api/v1/ready`
also verifies migrations, the durable worker heartbeat, pseudonym secrets, and
the adapters required by the selected mode. The Compose worker uses the
built-in offline adapters to recover feedback work. With
`RESEARCH_ENABLED=false`, model credentials and external research adapters are
not required for readiness; feedback remains deterministic and local.

Before enabling research or external model processing, configure and verify:

- `LLM_API_KEY`, `LLM_MODEL`, and the matching cost rates
- a reviewed production worker adapter factory
- `PRODUCTION_ADAPTERS_READY=true` only after those adapters are operational
- consent, roster, and research governance outside this Compose package

Treat `deploy/.env` as a secret-bearing operational file. Do not commit it,
copy it into an image, or include it in backups that lack equivalent access
controls.
