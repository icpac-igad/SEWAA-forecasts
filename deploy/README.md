# Cloud Run deployment

Production runs each forecast **channel** (dataset + accumulation — imerg-6h, imerg-24h,
rfe-24h, chirps-24h) as its own **Cloud Run Job**, triggered on a cron by **Cloud
Scheduler**, plus one Cloud Run **Service** that serves the resulting data as static files.
This swaps the local docker-compose topology's bind-mounted host directories
(`jobs` / `jobs-rfe` / `jobs-chirps` + `nginx` in `../docker-compose.yml`) for a GCS bucket
mounted via Cloud Run's native Cloud Storage FUSE volume support — no code changes needed,
`main.py`/`run_forecast.py` just write local files that happen to be backed by GCS.

One job per channel, not one job per dataset, so a slow or failing channel (e.g. CHIRPS
waiting on a slow upstream IFS mirror) never delays or queues behind another (e.g. IMERG's
6h products) — each is an independent Cloud Run Job execution with its own schedule.

## Why Jobs, not an always-on Service

`start_forecasting.py` is an infinite polling loop (`schedule` + `while True`), and Cloud Run
Services expect a container listening on `$PORT` — a permanently-running non-HTTP worker doesn't
fit that model well, and paying for 24/7 idle CPU to run `time.sleep()` is wasteful. `docker-compose.yml`'s
`jobs`/`jobs-rfe`/`jobs-chirps` services still run `start_forecasting.py` for that always-on
deployment; Cloud Run instead uses `auto_forecasts.py`, a one-shot equivalent scoped to a single
dataset+accumulation channel — it checks the last `--days_to_check` days for missing output and
generates only what's missing (via `run_forecast.py`'s own counts-file check), safe to call
repeatedly. So each Cloud Run Job just calls it once and exits:

```
--command=python --args=auto_forecasts.py,--dataset,imerg,--accumulation,6h
```

Cloud Scheduler re-invokes each job every 30 minutes — see `setup-cloud-scheduler.sh`.

## What's here

- `../cloudbuild.yaml` — builds the unified image once (used by all four jobs — `CGAN_DATASET`
  is a runtime env var, not a build arg) plus the nginx data-portal image, then deploys:
  `cgan-jobs-imerg-6h`, `cgan-jobs-imerg-24h`, `cgan-jobs-rfe-24h`, `cgan-jobs-chirps-24h`
  (Cloud Run Jobs), and `cgan-data-portal` (Cloud Run Service).
- `setup-cloud-scheduler.sh` — one-time (idempotent) setup of the four Cloud Scheduler triggers.

## Resource sizing (starting defaults — tune from Cloud Monitoring after real usage)

| Job | CPU | Memory | Timeout | Rationale |
|---|---|---|---|---|
| `cgan-jobs-imerg-24h`, `cgan-jobs-rfe-24h`, `cgan-jobs-chirps-24h` | 4 vCPU | 8 GiB | 3600s | CPU-only TensorFlow 2.15 inference (`pyproject.toml`, no CUDA in `Dockerfile`) over a 7-lead 24h ensemble (`run_forecast.py`) plus histogram post-processing — a real but modest batch workload. |
| `cgan-jobs-imerg-6h` | 8 vCPU | 32 GiB | 3600s | Same inference, but all 4 lead times (30/36/42/48h) run in one process (`forecast_date.py`'s loop) instead of one subprocess per lead — `gen.predict()`'s per-call memory growth (plain Python loop, no `tf.function`/batching) compounds across all 4x`ensemble_members: 1000` (`6h_accumulations/cGAN/dsrnngan/forecast.yaml`, kept at 1000 by design, not reduced). OOM'd in production at 8Gi/4vCPU — cpu raised alongside memory since Cloud Run ties the two. |
| `cgan-data-portal` | 1 vCPU | 512 MiB | — (Service) | Static file serving only. |

`--max-retries=1 --tasks=1 --parallelism=1` on every job matches `auto_forecasts.py`'s
single-process, sequential, idempotent-on-retry behavior — a retry just re-runs it, which
skips whatever already completed and exits non-zero only if a date/time in the range still
failed.

## Storage layout (proposed — confirm before first deploy)

One GCS bucket, structured exactly like the local `${STORE}` root in `../docker-compose.yml`/
`.env.example` — two top-level prefixes, `interface/` and `forecasts/`, with dataset (and for
`forecasts/`, accumulation period) as subdirectories under each:

```
gs://<bucket>/interface/imerg/...
gs://<bucket>/interface/rfe/...
gs://<bucket>/interface/chirps/...
gs://<bucket>/forecasts/imerg/6h/{cGAN_forecasts,IFS_forecast_data}/...
gs://<bucket>/forecasts/imerg/24h/{cGAN_forecasts,IFS_forecast_data}/...
gs://<bucket>/forecasts/rfe/24h/{cGAN_forecasts,IFS_forecast_data}/...
gs://<bucket>/forecasts/chirps/24h/{cGAN_forecasts,IFS_forecast_data}/...
```

Each Cloud Run Job mounts only the `only-dir` prefixes it needs via GCS FUSE
(`--add-volume ... mount-options=only-dir=<prefix>`); `cgan-data-portal` mounts the three
`interface-data` prefixes read-only and serves them at `/data/`, `/data/rfe/`, `/data/chirps/`
via `../configs/nginx.conf`.

**Open item:** the frontend (`cgan-cms/forecasts/templates/forecasts/forecasts_page.html:758-763`)
currently hardcodes production's data URL to an existing service,
`https://icpac-data-portal-8979869085.europe-west1.run.app/cgan-data/` — confirmed live to serve
IMERG-only data today, same directory shapes as `../configs/nginx.conf`. Whether that service
already reads from a bucket/prefix layout that should be reused (rather than the one proposed
here), or whether `cgan-data-portal` above is meant to replace it (requiring the frontend's
hardcoded URL to be updated), needs confirming with whoever owns that service — its source isn't
in this workspace, so this can't be resolved without that context.

## Before first deploy

Fill in / confirm:
- `PROJECT_ID`, `_REGION` (default `europe-west1`, matching the existing data portal's region)
- `_FORECAST_DATA_BUCKET` — create the bucket and the six `only-dir` prefixes above, or point at
  whatever bucket backs the existing `icpac-data-portal` (see Open item)
- A service account for Cloud Scheduler with `roles/run.invoker` on each Cloud Run Job
  (`SCHEDULER_SA` in `setup-cloud-scheduler.sh`)
- `../datasets/imerg/cGAN_data/{elev.nc,lsm.nc}` are present in the repo (shared by all three
  datasets via `datasets/{chirps,rfe}/cGAN_data` symlinks) — no action needed.
- `RFE_climatology_meansd_doy.nc` is still missing from the repo (needed by `cgan-jobs-rfe-24h`'s
  `run11` field set, via `data.py`'s `climatology_channel()` reading `CONSTANTS_PATH`). Deploy
  that file into the shared `cGAN_data` constants before `cgan-jobs-rfe-24h`'s first real run —
  it will fail with a `FileNotFoundError` until then.
