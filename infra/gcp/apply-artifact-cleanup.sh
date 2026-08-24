#!/usr/bin/env bash
# Idempotent. Needs artifactregistry.repositories.update on the lockin repo
# (roles/artifactregistry.repoAdmin). Keep policies win over delete policies,
# so :latest and the five newest digests survive even if they are older than
# 14 days.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
POLICY="${ROOT}/infra/gcp/artifact-registry-cleanup.json"

gcloud artifacts repositories set-cleanup-policies lockin \
  --project=lockin-505614 \
  --location=europe-west2 \
  --policy="${POLICY}" \
  --no-dry-run
