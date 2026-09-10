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

The smoke check requires the HTML shell, API liveness and every API readiness
check, including the worker and migration head. Allow startup to finish before
running it. Docker service health is liveness only: the backend must become live
before the worker starts, so using worker readiness as that dependency would deadlock.

The local example explicitly enables demo bootstrap. Its accounts use password
`quantumlearn-demo`:

- `student@quantumlearn.demo`
- `educator@quantumlearn.demo`
- `admin@quantumlearn.demo`

Demo login does not establish source-backed feature availability. New and legacy
material stays unavailable without matching clean scan receipts under the configured
policy. Follow the scanner provisioning section below before testing source-backed tasks.

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
The image normalises the entrypoint to Unix line endings so Windows checkouts can
build the same runnable package. Backup/restore modules are copied into the image.
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

## Source scanner provisioning

The backend image includes the local `clamscan` executable. It does not download
signatures or run a scanner daemon. An operations owner must provision and refresh
a Docker volume containing the ClamAV signature files, readable by UID 10001, at
`/var/lib/clamav`. Record the signature version/date, scanner version, policy owner
and actual policy approval. Set these environment values:

```dotenv
MATERIAL_SCAN_POLICY=required
MATERIAL_SCAN_POLICY_VERSION=<approved-policy-reference>
MATERIAL_CLAMSCAN_PATH=/usr/bin/clamscan
CLAMAV_SIGNATURE_VOLUME=<provisioned-signature-volume>
MATERIAL_SCAN_TIMEOUT_SECONDS=60
MATERIAL_SCAN_DATABASE_MAX_AGE_DAYS=7
```

Add `-f deploy/compose.scanner.yaml` after the other Compose files for **every**
service start/recreation. It mounts the same signatures read-only in API and worker.
For example, validate the configuration with:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.hosted.yaml -f deploy/compose.scanner.yaml config --quiet
```

`disabled` is the safe default and quarantines intake; it does not skip scanning.
Missing executable, unsupported scanner options, missing/stale signatures, scan
timeout, suspicious files and scanner errors prevent publication. Confirm clean,
quarantined and unavailable outcomes using synthetic local files after provisioning.
Do not create clean receipts for legacy materials without rescanning their actual bytes.
Infrastructure `/ready` does not certify scanner/source availability. On local
Windows launches, configure an operator-provisioned absolute executable path and
its default signature directory in the backend environment; no global installation
is performed by the launcher.

## Release backup and rollback candidate

Run the following from `src-main`. Retain the exact backend/frontend image IDs or
digests, release commit, environment reference and migration head in the operations
record. Protect a backup directory outside the data volume; on Linux it must be
writable by container UID 10001. Keep secret backups separate and access-controlled.

Close ingress and stop the owned deployment's writers before capture:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.hosted.yaml stop frontend backend worker
python scripts/release_operations.py backup --env-file deploy/.env --hosted --output /srv/learnlens-backups
```

Omit the hosted overlay and `--hosted` for the local package. The command refuses
running API/worker services, disables migrations and demo bootstrap, and invokes
the image's shipped backup module against the effective database/upload paths.
It verifies the complete bundle and an isolated restore before reporting its path.
It does not restart services. Keep writers stopped for an upgrade or restart the
same recorded package explicitly if capture was a routine maintenance operation.

Prepare a rollback with the retained backend image and its corresponding bundle:

```sh
python scripts/release_operations.py prepare-rollback --bundle /srv/learnlens-backups/learnlens-BUNDLE --image quantumlearn-backend:RETAINED_TAG --volume learnlens_restore_candidate
```

This refuses an existing volume or a mismatched image/backup migration head. It
never pulls/builds an image, downgrades a database, deletes a volume, or switches
the deployment. It creates a verified candidate in a fresh volume with network
disabled. A failed candidate is left isolated for inspection; choose a new name
for a later attempt. The retained image must include these operational tools.

Copy the deployment environment into a restricted candidate file and apply the
printed database/upload/volume values. Set `IMAGE_TAG` to the retained release,
`MIGRATE_ON_START=false`, `BOOTSTRAP_DEMO=false`, and `RESEARCH_ENABLED=false`.
Retain both matching images. Verify source/assessment/evidence histories, worker
recovery and permissions; reconcile all withdrawal, revocation, hold and retention
events newer than the snapshot against the authoritative records before any
research processing. Do not merge databases by copying individual rows.

At an authorised cutover, keep ingress closed, stop the current services, and
recreate from the candidate configuration using `up -d --no-build --pull never`
with the same overlays (including scanner where provisioned). Run the smoke check
and the approved functional spot checks before reopening ingress. Keep the old
volume untouched. Do not use Alembic downgrade to erase protected history.
The script prepares a candidate; it does not establish hosted rollback acceptance.

See the [operational acceptance checklist](../../docs/learnlens/operational-acceptance-checklist.md)
for required external records and final combined validation scope.

## Verification scope — 11 September 2026

Starting application commit: `ecd14f62abc57149edef17ab08f8367b1c199eda`.
The 12 release-package and 13 conditional-module cases have passing outcomes
across focused runs; the final conditional journey passed in 8.68 seconds.
Checks cover missing/stale readiness, isolated copied backup CLI import, stopped
writer enforcement, fresh restore volume, image/head mismatch, backup command
syntax and the second-domain service journey. Reproduce from the backend with
`python -m pytest tests/test_release_package.py tests/test_conditional_programming.py -q`.
Use the checkout's backend/tests on `PYTHONPATH` and a short writable temporary
directory on Windows. Initial temporary-directory access and fixture setup
failures were corrected without changing application gates.

Ruff lint/format and base, scanner-overlay and hosted-overlay Compose configuration
checks pass. The local Docker CLI could not connect to its Linux engine, so image
build, entrypoint execution, actual ClamAV/signatures, container volume permissions,
container backup/rollback and local/hosted package smoke remain **unverified**.
No service was deployed and the existing seven-case recovery drill was not repeated.
