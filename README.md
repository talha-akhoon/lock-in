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
   Each goal has a tracking method (see below). When you add a goal, record
   where you are now. On a running total that amount already counts; on a
   number-to-target goal it is the line progress is measured from. Goals can
   be required (they
   decide the forfeit) or optional (they only affect your percentage). A goal
   can be visible to the team or private — private goals still count, but
   teammates see aggregates only, never the title or values.
5. **Commit.** After a short submission window the commitment locks. Titles,
   targets and descriptions become final, and goals can no longer be removed.
   You can still **add** new goals or sub-steps right up until the challenge
   ends — adding only strengthens the commitment — and a goal added after the
   lock joins it immediately. Visibility and display order can still change. An
   admin can temporarily reopen a commitment; that is audited.
6. **Starting point.** You set where you are now on each goal when you write
   it. If the challenge has not started yet, Check-In also lets you update
   that snapshot.
7. **Check in.** Each day you update the goals that moved. Streaks and a
   heatmap use the challenge's own timezone. Each log pings teammates in the
   app and, if they turned on push, on their phone — so one more LC problem
   is one more nudge. A save that finishes a team-visible goal sends the
   completion ping only, not a second "logged progress" banner.
   An hourly job also pings you in the evening (the challenge timezone) if you
   have not checked in, if a streak is about to die, if a teammate has gone
   quiet for three days, or (Sunday evening) if a required goal is behind the
   expected pace. Deadline reminders — goals lock tomorrow, 100 / 30 / 7 days
   left, challenge finished — go out as push too, so they reach people who
   have not opened the app. Mute any type in Settings.
8. **Optional: connect your own LLM.** ChatGPT custom connectors use OAuth:
   paste the `/mcp` URL, choose OAuth, sign in to LockIn and approve. Cursor
   and Claude take a personal token from Settings. The model can read your
   goals, see teammates' team-visible progress, add goals and sub-steps (even
   after the lock, until the challenge ends), edit your goals before the lock,
   and log today's check-in. Once locked it cannot change your wording or
   targets. LockIn stays the source of truth. Connecting shares your view of
   the team with that LLM provider. Private goals stay in LockIn.
9. **Finish.** When the end date passes, required goals are scored. Anyone who
   fell short owes the forfeit to each other member. The results screen lists
   who pays whom.

## Features

### Goals

- Four tracking methods — pick what check-in will ask:
  - **Done or not done** — a single tick (get promoted, ship the app).
  - **Update the current figure** — what is the number now (deadlift 180kg,
    body fat to 12%). Not for sessions or kilometres you add up.
  - **Add today's amount** — how much you did today (150 pages, 100 gym
    sessions). Not for a lift, weight, or time you re-measure.
  - **Set a percentage yourself** — type 0–100 when you think you have
    moved (a side project you cannot count cleanly).
- **Steps** — optional one-level sub-goals. You check in on the steps; the
  parent averages its required children. Use this when the work is a few named
  finish-lines, not when you already have a running total.
- In-app **?** buttons next to tracking method and Add step explain the above.

### Daily accountability

- **Starting point** — when you add a goal, set where you are now. On a
  running total that amount already counts; on a number-to-target goal it is
  the line progress is measured from. Before kick-off you can still update
  it from Check-In.
- Date-stamped check-ins, including a note.
- Per-member heatmap and streak on the profile.
- Team dashboard with everyone's progress (private titles redacted).
- Activity feed of recent updates.
- **Install as an app** — add LockIn to the Home Screen or desktop. Settings
  turns on push so teammate logs, missed check-ins, streaks, pace and
  deadline reminders reach you when the tab is closed. Mute individual types
  there: off means no bell and no push for that event. iPhone only delivers
  push after you add LockIn to the Home Screen. Private goal titles are never
  included.

### MCP

A remote MCP endpoint at `/mcp` so a member can connect their own LLM.

- **ChatGPT** — custom connectors only support no auth, OAuth, or mixed auth.
  LockIn uses OAuth. In ChatGPT, add a connector with `https://your-origin/mcp`
  and choose OAuth. You sign in to LockIn and approve; ChatGPT never sees a
  pasted token.
- **Cursor and Claude** — Settings issues a personal token. Paste the JSON
  config (URL plus `Authorization: Bearer`). The token is shown once.
- Read your own goals and progress, including private ones.
- Read the team standings, a teammate's profile, and the activity feed — the
  same privacy as the app. Private titles, descriptions, targets and values
  are never sent. Team-visible teammate goals are included on purpose, so the
  model can compare and motivate.
- Add goals and sub-steps any time until the challenge ends, even after your
  commitment locks — adding only strengthens it. Editing wording or targets is
  only possible before the lock; once locked, the model can change just
  visibility and ordering, and can never remove a goal.
- Log today's check-in.
- Revoke a token from Settings if it leaks (OAuth connections appear as
  “ChatGPT”). Connecting shares that member's view of the team with their LLM
  provider.

### Team and admin

- Invite codes shown in full once; only a prefix is stored.
- Admin screens: team, challenge (dates, forfeit, description), invitations,
  members (role change and removal), and an audit log.
- Nine audited actions, including invites, role changes, challenge amendments
  and goal-unlock overrides.

### Notifications

In-app (no email): goal-lock warnings, challenge milestones (100 / 30 / 7
days), challenge complete, a teammate logging progress, a teammate finishing a
goal, a member joining, you have not checked in today (evening, challenge
timezone), a streak about to die, a teammate gone quiet for three days, and
behind on a required goal (Sunday evening, after a week's grace). A save that
finishes a team-visible goal sends only the completion ping, not a second
progress ping. Mute any of those in Settings — muted types skip the bell and
push.

Every type except "someone joined" also goes out as Web Push to devices that
have it enabled. An hourly GitHub Action calls an internal dispatch endpoint
so people who have not opened the app still get lock-screen pings in the
challenge's own evening, not 20:00 UTC. Locally you can hit the same endpoint
with `X-LockIn-Dispatch` (HMAC of `SECRET_KEY`).

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
- `SECRET_KEY` — any long random string locally. Rotating it signs everyone out
  and invalidates push subscriptions (VAPID keys are derived from it).
- `CHALLENGE_TIMEZONE` — default zone for new challenges (`Europe/London` is
  fine). Check-in days and streaks use the *challenge's* zone, not the
  server's.
- `PUBLIC_ORIGIN` — optional locally. The public HTTPS origin ChatGPT should
  use for OAuth metadata (for example a tunnel URL). Empty means derive it
  from `Host` / `X-Forwarded-*`.

`DATABASE_URL` in `.env.example` is for the Compose network. Leave it as-is
when you run Docker.

### 2. Git hooks

Install once so Ruff, oxlint, and `tsc` run before each commit (needs `uv`
and `npm` on the host):

```bash
uvx pre-commit install
```

The hook auto-formats staged backend files. If it changes something, `git add`
those files and commit again. Tests stay in CI — they need Postgres.

### 3. Google OAuth

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

### 4. Start the stack

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

### 5. Production-shaped image (optional)

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
npm run typecheck
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
                          notification dispatch, audit, progress, clock, MCP
                          tokens, OAuth, Web Push
  api/oauth.py            ChatGPT MCP connector OAuth (well-known, authorize, token)
  mcp/                    Streamable HTTP tools at /mcp; same privacy as the app
  models/domain.py        SQLAlchemy models
  dependencies/           auth, membership, CSRF

frontend/src/
  pages/                  one file per screen, including /admin/*
  features/               goal forms, check-in payloads, help copy
  components/             primitives, heatmap, countdown, notifications, InfoTip, PWA settings, mute toggles
  hooks/queries.ts        typed TanStack Query hooks
  lib/                    API client, types, formatting, category metadata, Web Push
frontend/public/          web app manifest, service worker, icons
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

Every push to `main` that passes CI is built and deployed by the `deploy`
job in `.github/workflows/ci.yml`. Manual emergency deploys: Actions →
**Deploy**, or:

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --service-account=projects/lockin-505614/serviceAccounts/lockin-run@lockin-505614.iam.gserviceaccount.com \
  --substitutions "_GOOGLE_CLIENT_ID=YOUR_PUBLIC_CLIENT_ID,_IMAGE=europe-west2-docker.pkg.dev/lockin-505614/lockin/app:latest"
gcloud run deploy lockin \
  --image "europe-west2-docker.pkg.dev/lockin-505614/lockin/app:latest" \
  --region europe-west2 \
  --service-account=lockin-run@lockin-505614.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --set-env-vars "ENVIRONMENT=production,SECURE_COOKIES=true,FRONTEND_DIST=/frontend/dist,CHALLENGE_TIMEZONE=Europe/London,PUBLIC_ORIGIN=https://lockin.talhaakhoon.dev" \
  --set-secrets "DATABASE_URL=lockin-database-url:latest,SECRET_KEY=lockin-secret-key:latest,GOOGLE_CLIENT_ID=lockin-google-client-id:latest"
```

`max-instances=1` avoids concurrent Alembic runs. Move migrations to a Cloud
Run Job before raising that limit. Add the `run.app` URL and the custom domain
to the OAuth client's authorised origins.

### GitHub Actions (CI, deploy, backups, nudges)

CI (`.github/workflows/ci.yml`) runs on every push and pull request. On
`main`, after tests and the image smoke check pass, the same workflow pushes
the image to Artifact Registry and updates Cloud Run. The Cloudflare Worker
is deployed separately with Wrangler, not from Actions. **Deploy** is a
manual-only fallback. **Notifications** (`.github/workflows/notifications.yml`)
runs hourly: the app only sends evening nudges when the *challenge*
timezone is at or after 20:00, so a Tokyo team is pinged at Tokyo evening
rather than 05:00. It mints a Google ID token for `lockin-github` (audience
`https://lockin.talhaakhoon.dev`) and POSTs
`/api/v1/internal/notifications/dispatch`. No extra secret.

Create a deploy identity once. The org blocks service-account JSON keys
(`iam.disableServiceAccountKeyCreation`), so GitHub impersonates
`lockin-github` through Workload Identity Federation — no key file.
Do not reuse `lockin-run` for this; that account is what the running service
uses to read production secrets. Skip any `create` command that says the
resource already exists.

```bash
gcloud iam service-accounts create lockin-github \
  --project=lockin-505614 \
  --display-name="LockIn GitHub Actions"

gcloud artifacts repositories add-iam-policy-binding lockin \
  --project=lockin-505614 \
  --location=europe-west2 \
  --member="serviceAccount:lockin-github@lockin-505614.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding lockin-505614 \
  --member="serviceAccount:lockin-github@lockin-505614.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding \
  lockin-run@lockin-505614.iam.gserviceaccount.com \
  --member="serviceAccount:lockin-github@lockin-505614.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud storage buckets create gs://lockin-505614-backups \
  --project=lockin-505614 \
  --location=europe-west2 \
  --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding gs://lockin-505614-backups \
  --member="serviceAccount:lockin-github@lockin-505614.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud services enable iamcredentials.googleapis.com sts.googleapis.com \
  --project=lockin-505614

gcloud iam workload-identity-pools create github \
  --project=lockin-505614 \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --project=lockin-505614 \
  --location=global \
  --workload-identity-pool=github \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='talha-akhoon/lock-in'"

gcloud iam service-accounts add-iam-policy-binding \
  lockin-github@lockin-505614.iam.gserviceaccount.com \
  --project=lockin-505614 \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/979991728317/locations/global/workloadIdentityPools/github/attribute.repository/talha-akhoon/lock-in"
```

No `GCP_SA_KEY` secret. Repository secrets (GitHub → Settings → Secrets and
variables → Actions — `gh` is not required):

| Secret | Used by | Value |
| --- | --- | --- |
| `BACKUP_DATABASE_URL` | Backups | Neon **direct** `postgresql://…?sslmode=require` |
| `BACKUP_ENCRYPTION_KEY` | Backups | Long passphrase also stored offline |

After changing secrets, run **Weekly database backup** from the Actions tab
once to prove the dump path.

### Cloudflare custom domain

Point the domain's nameservers at Cloudflare, set `ORIGIN_HOST` and the route
in `infra/cloudflare/wrangler.toml`, then:

```bash
cd infra/cloudflare
npx wrangler deploy
```

The session cookie is host-only, secure, HTTP-only and SameSite Lax. Do not set
an explicit cookie domain.

### Backups

`.github/workflows/backup.yml` dumps weekly (and on demand), verifies the
archive decrypts, keeps a copy as a 90-day Actions artifact, and copies it to
`gs://lockin-505614-backups`.

`BACKUP_DATABASE_URL` is not the app's `DATABASE_URL`: `pg_dump` rejects the
`+psycopg` driver suffix, so store Neon's **direct** `postgresql://` string.

Read `docs/restore-runbook.md` and run the drill before a real challenge
starts. With a cash forfeit on the line, an untested backup does not count.

## Security model

- Team queries are scoped to an active membership. Cross-team URL tampering
  returns 403 or 404.
- Admin actions require an admin membership and write an audit row that names
  the actor.
- State-changing requests need a double-submit CSRF token.
- The hourly notification dispatch is not a browser session: locally it
  accepts `X-LockIn-Dispatch` (HMAC of `SECRET_KEY`); in production it
  accepts a Google ID token from `lockin-github`. It is not CSRF-gated.
- MCP access is a revocable personal token. ChatGPT obtains one through
  OAuth (PKCE); Cursor and Claude paste one from Settings.
- Committed goals are immutable except visibility and sort order, unless an
  admin override reopens them (audited).

## Contributing

`AGENTS.md` is the working agreement for humans and coding agents: keep this
README in lockstep with the product. If you add, change, or remove a
user-facing behaviour, update the **How it works** and **Features** sections in
the same change.
