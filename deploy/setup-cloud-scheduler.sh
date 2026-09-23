#!/usr/bin/env bash
# Creates (or updates) the four Cloud Scheduler jobs that trigger the Cloud Run Jobs
# deployed by ../cloudbuild.yaml — one per forecast channel (dataset + accumulation):
# cgan-jobs-imerg-6h / cgan-jobs-imerg-24h / cgan-jobs-rfe-24h / cgan-jobs-chirps-24h.
#
# Run once per environment, after the Cloud Run Jobs themselves exist (cloudbuild.yaml
# deploys those). Safe to re-run — uses `scheduler jobs update || create` per job.
#
# Cadence: every 30 minutes for all four. auto_forecasts.py is idempotent (run_forecast.py
# skips already-computed output), so a no-op check every 30 min is cheap — Cloud Run Jobs
# only bill for actual execution time. Each channel is its own job/schedule so a slow or
# failing channel never delays another's trigger.
#
# Required env vars (fill in before running):
#   PROJECT_ID   GCP project hosting the Cloud Run jobs
#   REGION       e.g. europe-west1 (must match cloudbuild.yaml's _REGION)
#   SCHEDULER_SA scheduler-invoker service account email, with roles/run.invoker on each
#                job (create once: gcloud iam service-accounts create scheduler-invoker)

set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
: "${REGION:?Set REGION}"
: "${SCHEDULER_SA:?Set SCHEDULER_SA to a service account email with roles/run.invoker on each job}"

for CHANNEL in imerg-6h imerg-24h rfe-24h chirps-24h; do
  JOB="cgan-jobs-${CHANNEL}"
  URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"

  echo "Wiring Cloud Scheduler -> ${JOB} (every 30 min)"
  if gcloud scheduler jobs describe "${JOB}-trigger" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${JOB}-trigger" \
      --location="${REGION}" --project="${PROJECT_ID}" \
      --schedule="*/30 * * * *" \
      --uri="${URI}" \
      --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_SA}"
  else
    gcloud scheduler jobs create http "${JOB}-trigger" \
      --location="${REGION}" --project="${PROJECT_ID}" \
      --schedule="*/30 * * * *" \
      --uri="${URI}" \
      --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_SA}"
  fi
done
