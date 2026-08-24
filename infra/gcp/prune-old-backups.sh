#!/usr/bin/env bash
# Delete gs://lockin-505614-backups/lockin-YYYY-MM-DD.sql.gz.enc older than 90
# days. GitHub Actions artifacts already expire at 90 days; this keeps GCS in
# line so backup storage cannot grow without bound.
set -euo pipefail

BUCKET="${BACKUP_BUCKET:-gs://lockin-505614-backups}"
cutoff="$(date -u -d '90 days ago' +%Y-%m-%d)"
echo "Pruning backups in ${BUCKET} older than ${cutoff}"

mapfile -t objects < <(gcloud storage ls "${BUCKET}/" || true)
if [ "${#objects[@]}" -eq 0 ]; then
  echo "Bucket is empty."
  exit 0
fi

deleted=0
for uri in "${objects[@]}"; do
  [ -n "${uri}" ] || continue
  base="${uri##*/}"
  case "${base}" in
    lockin-????-??-??.sql.gz.enc) ;;
    *)
      echo "Skipping unexpected object ${uri}"
      continue
      ;;
  esac
  day="${base#lockin-}"
  day="${day%.sql.gz.enc}"
  if [[ "${day}" < "${cutoff}" ]]; then
    echo "Deleting ${uri}"
    gcloud storage rm "${uri}"
    deleted=$((deleted + 1))
  fi
done

echo "Deleted ${deleted} old backup(s)."
