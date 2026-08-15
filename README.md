# LockIn

LockIn is a private team accountability app for one fixed challenge at a time —
typically six months. You write down measurable goals, lock them in, check in
daily, and your teammates can see whether you are doing what you said you would.
If a required goal is still unfinished when the challenge ends, you owe the
configured forfeit to every other member.

There is no chat, no public profile, and no payment processing. The product is
the commitment, the daily record, and the reckoning at the end.

## How it works

1. **Sign in with Google.** Unverified Google emails are rejected. Your Google
   `sub`, not your email, is the identity key.
2. **Create a team or redeem an invite.** A person can only be active in one
   team at a time. The first member becomes the admin.
3. **Start a challenge.** A team has at most one open challenge (`DRAFT`,
   `UPCOMING`, or `ACTIVE`). Completed challenges stay visible as history.
4. **Write goals.** Five areas: Religious, Physical, Career, Business, Personal.
   Each goal has a tracking method (see below). Goals can be required (they
   decide the forfeit) or optional (they only affect your percentage). A goal
   can be visible to the team or private — private goals still count, but
   teammates see aggregates only, never the title or values.
5. **Commit.** After a short submission window the commitment locks. Titles,
   targets and descriptions become final. Visibility and display order can
   still change. An admin can temporarily reopen a commitment; that is audited.
6. **Check in.** Each day you update the goals that moved. Streaks and a
   heatmap use the challenge's own timezone.
7. **Finish.** When the end date passes, required goals are scored. Anyone who
   fell short owes the forfeit to each other member. The results screen lists
   who pays whom.

## Features

### Goals

- Four tracking methods — pick how you will *know* you are done:
  - **Done or not done** — a single tick (get promoted, ship the app).
  - **A number moving to a target** — record the current figure (deadlift
    180kg, body fat to 12%).
  - **A running total** — add what you did today (150 pages of reading, 12
    books).
  - **A percentage you set yourself** — type 0–100 when you think you have
    moved (a side project you cannot count cleanly).
- **Steps** — optional one-level sub-goals. You check in on the steps; the
  parent averages its required children. Use this when the work is a few named
  finish-lines, not when you already have a running total.
- In-app **?** buttons next to tracking method and Add step explain the above.

### Daily accountability

- Date-stamped check-ins, including a note.
- Per-member heatmap and streak on the profile.
- Team dashboard with everyone's progress (private titles redacted).
- Activity feed of recent updates.

### Team and admin

- Invite codes shown in full once; only a prefix is stored.
- Admin screens: team, challenge (dates, forfeit, description), invitations,
  members (role change and removal), and an audit log.
- Nine audited actions, including invites, role changes, challenge amendments
  and goal-unlock overrides.

### Notifications

In-app only (no email): goal-lock warnings, challenge milestones (100 / 30 / 7
days), challenge complete, a teammate finishing a goal, and a member joining.

## Later

- **MCP server** (not built) — a thin pipe so a member can connect their own
  LLM (Claude, ChatGPT, and similar) to log today’s check-in and read their
  own goals and progress for planning. LockIn stays the source of truth; the
  model does the coaching. Same lock and privacy rules as the app. Connecting
  shares that member’s goal data with their LLM provider. Do not expose
  teammate private goals or let the model edit locked targets.

## Local setup

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
a Google Cloud project so you can sign in.

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_ORG/lockin.git
cd lockin
cp .env.example .env
```

Edit `.env`:

- `GOOGLE_CLIENT_ID` — the OAuth **Web client** ID (public; also sent to the
  browser as `VITE_GOOGLE_CLIENT_ID`).
- `SECRET_KEY` — any long random string locally. Rotating it signs everyone out.
- `CHALLENGE_TIMEZONE` — default zone for new challenges (`Europe/London` is
  fine). Check-in days and streaks use the *challenge's* zone, not the
  server's.

`DATABASE_URL` in `.env.example` is for the Compose network. Leave it as-is
when you run Docker.

### 2. Google OAuth

1. In [Google Cloud Console](https://console.cloud.google.com/) create (or
   pick) a project.
2. APIs & Services → OAuth consent screen. External is fine for local use.
3. Credentials → Create credentials → OAuth client ID → **Web application**.
4. Authorised JavaScript origins:
   - `http://localhost:5173` (Compose / Vite)
   - `http://127.0.0.1:5173`
5. You do not need a redirect URI for Google Identity Services; LockIn verifies
   the ID token on the server.
6. Paste the client ID into `.env` as `GOOGLE_CLIENT_ID`.

Without this, the login page renders but the sign-in button stays disabled
(`Add VITE_GOOGLE_CLIENT_ID to enable sign-in`).

### 3. Start the stack

```bash
docker compose up --build
```

| What        | URL                         |
| ----------- | --------------------------- |
| App         | http://localhost:5173       |
| API         | http://localhost:8000       |
| API schema  | http://localhost:8000/docs  |
| Postgres    | `localhost:5433`            |

Postgres is published on **5433** so it does not collide with a local install
on 5432. The schema browser is off when `ENVIRONMENT=production`.

The first person to sign in can create a team and a challenge — no seed data
required. To load a representative mid-challenge team instead:

```bash
docker compose exec backend python -m app.seed
```

The seed script refuses to run against an unmigrated database.

After changing `GOOGLE_CLIENT_ID`, restart the frontend container so Vite
picks up `VITE_GOOGLE_CLIENT_ID`.

### 4. Production-shaped image (optional)

The root `Dockerfile` is what you would deploy: one container, built SPA + API,
non-root, docs off.

```bash
docker build -t lockin:local .
docker run --rm -p 8081:8080 --network lockin_default \
  -e DATABASE_URL=postgresql+psycopg://lockin:lockin@postgres:5432/lockin \
  -e SECRET_KEY=dev-only \
  -e GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" \
  lockin:local
```

Then open http://localhost:8081. That origin serves `/dashboard` and
`/api/v1` together.

## Tests and checks

Backend tests need Postgres. Inside Compose:

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
```

On the host, point them at an empty database — the suite migrates and truncates
it between tests:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://lockin:lockin@127.0.0.1:5433/lockin \
  uv run pytest --cov=app
uv run ruff check .
uv run ruff format --check .
uv run alembic check          # models still match migrations
```

```bash
cd frontend
npm ci
npm run test
npm run lint
npm run build
```

CI (`.github/workflows/ci.yml`) runs the above on every push, then builds the
production image and checks single-origin serving, a non-root user, and disabled
docs.

## Architecture

```
backend/app/
  api/v1/routes/          one module per resource; handlers stay thin
  api/v1/serializers.py   response shaping, including the privacy boundary
  services/               goals, check-ins, challenges, teams, notifications,
                          audit, progress, clock
  models/domain.py        SQLAlchemy models
  dependencies/           auth, membership, CSRF

frontend/src/
  pages/                  one file per screen, including /admin/*
  features/               goal forms, check-in payloads, help copy
  components/             primitives, heatmap, countdown, notifications, InfoTip
  hooks/queries.ts        typed TanStack Query hooks
  lib/                    API client, types, formatting, category metadata
```

**Privacy:** a teammate viewing a `PRIVATE` goal gets counts only. Every
cross-user response goes through
`serializers.goal_tree(..., viewer_is_owner=False)`. Held in place by
`backend/tests/test_privacy.py` and
`frontend/src/pages/MemberProfilePage.test.tsx`.

**Invariants:** one active team per user, and one open challenge per team, are
enforced by partial unique indexes *and* service-layer 409s.

Stack: FastAPI + SQLAlchemy 2 + Alembic + Postgres 17, React + TypeScript +
Vite + TanStack Query + Tailwind.

## Production deployment

Designed to run near £0/month: Cloud Run + Neon + a Cloudflare Worker in front
of a custom domain. Details below; you do not need them to develop locally.

### Neon

1. Create a free Neon project.
2. App URL: take the **pooled** string, replace `postgresql://` with
   `postgresql+psycopg://`, keep `?sslmode=require`.
3. Backups: take the **direct** (non-pooled) string, unmodified.
4. Leave scale-to-zero on.

### Google Cloud Run

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions "_GOOGLE_CLIENT_ID=YOUR_PUBLIC_CLIENT_ID,_IMAGE=us-central1-docker.pkg.dev/PROJECT_ID/lockin/app:latest"
gcloud run deploy lockin \
  --image "us-central1-docker.pkg.dev/PROJECT_ID/lockin/app:latest" \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --set-env-vars "ENVIRONMENT=production,SECURE_COOKIES=true,FRONTEND_DIST=/frontend/dist,CHALLENGE_TIMEZONE=Europe/London" \
  --set-secrets "DATABASE_URL=lockin-database-url:latest,SECRET_KEY=lockin-secret-key:latest,GOOGLE_CLIENT_ID=lockin-google-client-id:latest"
```

`max-instances=1` avoids concurrent Alembic runs. Move migrations to a Cloud
Run Job before raising that limit. Add the `run.app` URL and the custom domain
to the OAuth client's authorised origins.

### Cloudflare custom domain

Point the domain's nameservers at Cloudflare, then deploy `infra/cloudflare/`:

```bash
cd infra/cloudflare
# Set ORIGIN_HOST and the route pattern in wrangler.toml first.
npx wrangler deploy
```

The session cookie is host-only, secure, HTTP-only and SameSite Lax. Do not set
an explicit cookie domain.

### Backups

`.github/workflows/backup.yml` dumps weekly, verifies the archive decrypts, and
keeps it for 90 days. Secrets:

- `BACKUP_DATABASE_URL` — Neon's **direct** `postgresql://` URL. `pg_dump`
  rejects the `+psycopg` suffix, so this is not `DATABASE_URL`.
- `BACKUP_ENCRYPTION_KEY` — a long passphrase stored outside GitHub.

Read `docs/restore-runbook.md` and run the drill before a real challenge
starts. With a cash forfeit on the line, an untested backup does not count.

## Security model

- Team queries are scoped to an active membership. Cross-team URL tampering
  returns 403 or 404.
- Admin actions require an admin membership and write an audit row that names
  the actor.
- State-changing requests need a double-submit CSRF token.
- Committed goals are immutable except visibility and sort order, unless an
  admin override reopens them (audited).

## Contributing

`AGENTS.md` is the working agreement for humans and coding agents: keep this
README in lockstep with the product. If you add, change, or remove a
user-facing behaviour, update the **How it works** and **Features** sections in
the same change.
