# Agent notes

LockIn is a private team accountability app. Product purpose, the user loop,
the feature list, and local setup live in `README.md`. Read that first.

## Keep the README honest

`README.md` is what a new contributor opens. Treat it as part of the product.

Update `README.md` in the **same change** when you:

- add a user-facing feature or screen
- change how an existing feature works (tracking methods, steps, locking,
  privacy, forfeits, invites, notifications, admin, auth)
- remove or hide a feature
- change local setup (ports, env vars, Docker, OAuth, seed, test commands)
- change deploy, backup, or security assumptions that the README states

Do not leave the README describing a button, rule, or flow that no longer
exists. Do not ship a new flow that the **How it works** or **Features**
sections would not mention.

Out of scope stays out of scope unless the change deliberately adds it:
payments, chat, comments, reactions, mobile app, AI coaching, third-party
integrations, public profiles, email notifications.

## Working conventions

- Do not edit plan files the user attached unless they ask.
- Do not commit unless the user asks.
- Backend: FastAPI handlers stay thin; logic lives in `backend/app/services/`.
  Private goals are redacted only in `serializers.goal_tree`.
- Frontend: pages in `frontend/src/pages/`, typed hooks in
  `frontend/src/hooks/queries.ts`. User-facing help copy lives in
  `frontend/src/lib/help.ts` — if you change a tracking method or steps, update
  that file **and** the README feature list.
- One active team per user and one open challenge per team are database
  invariants. Do not weaken the partial unique indexes.
