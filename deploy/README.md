# Cloud Run deployment

Production runs each forecast **channel** (dataset + accumulation — imerg-6h, imerg-24h,
rfe-24h, chirps-24h) as its own **Cloud Run Job**, triggered on a cron by **Cloud
Scheduler**, plus one Cloud Run **Service** that serves the resulting data as static files.
This swaps the local docker-compose topology's bind-mounted host directories
(`imerg` / `rfe` / `chirps` + `nginx` in `../docker-compose.yml`) for a GCS bucket
mounted via Cloud Run's native Cloud Storage FUSE volume support — no code changes needed,
`main.py`/`run_forecast.py` just write local files that happen to be backed by GCS.

One job per channel, not one job per dataset, so a slow or failing channel (e.g. CHIRPS
waiting on a slow upstream IFS mirror) never delays or queues behind another (e.g. IMERG's
6h products) — each is an independent Cloud Run Job execution with its own schedule.
IMERG 6h is split further, into one job per IFS initialisation time (`cgan-jobs-imerg-6h-00z`/
`-06z`/`-12z`/`-18z`, each running `auto_forecasts.py ... --time <HHMM>`), so the four init
times generate in parallel instead of one after another.

## Why Jobs, not an always-on Service

`start_forecasting.py` is an infinite polling loop (`schedule` + `while True`), and Cloud Run
Services expect a container listening on `$PORT` — a permanently-running non-HTTP worker doesn't
fit that model well, and paying for 24/7 idle CPU to run `time.sleep()` is wasteful. `docker-compose.yml`'s
`imerg`/`rfe`/`chirps` services still run `start_forecasting.py` for that always-on
deployment; Cloud Run instead uses `auto_forecasts.py`, a one-shot equivalent scoped to a single
dataset+accumulation channel — it checks the last `--days_to_check` days for missing output and
generates only what's missing (via `run_forecast.py`'s own counts-file check), safe to call
repeatedly. So each Cloud Run Job just calls it once and exits:

```
--command=python --args=auto_forecasts.py,--dataset,imerg,--accumulation,6h
```

Cloud Scheduler re-invokes each job every 30 minutes — see `setup-cloud-scheduler.sh`.

## What's here

- `../cloudbuild.yaml` — builds the unified image once (used by every job — `CGAN_DATASET`
  is a runtime env var, not a build arg) plus the nginx data-portal image, then deploys:
  `cgan-jobs-imerg-6h-{00z,06z,12z,18z}`, `cgan-jobs-imerg-24h`, `cgan-jobs-rfe-24h`, `cgan-jobs-chirps-24h`
  (Cloud Run Jobs), and `cgan-data-portal` (Cloud Run Service).
- `setup-cloud-scheduler.sh` — one-time (idempotent) setup of one Cloud Scheduler trigger per job.
  Replacing the single `cgan-jobs-imerg-6h` job doesn't remove it or its
  `cgan-jobs-imerg-6h-trigger` — delete both by hand, or the old job keeps running every 30 min.

## Resource sizing (starting defaults — tune from Cloud Monitoring after real usage)

| Job | CPU | Memory | Timeout | Rationale |
|---|---|---|---|---|
| `cgan-jobs-imerg-24h`, `cgan-jobs-rfe-24h`, `cgan-jobs-chirps-24h` | 4 vCPU | 8 GiB | 3600s | CPU-only TensorFlow 2.15 inference (`pyproject.toml`, no CUDA in `Dockerfile`) over a 7-lead 24h ensemble (`run_forecast.py`) plus histogram post-processing — a real but modest batch workload. |
| `cgan-jobs-imerg-6h-00z`, `-06z`, `-12z`, `-18z` | 4 vCPU | 16 GiB | 3600s | Same inference, one IFS init time per job, but each run still does all 4 lead times (30/36/42/48h) in one process (`forecast_date.py`'s loop) — `gen.predict()`'s per-call memory growth (plain Python loop, no `tf.function`/batching) compounds across all 4x`ensemble_members: 1000` (`6h_accumulations/cGAN/dsrnngan/forecast.yaml`, kept at 1000 by design, not reduced). OOM'd in production at 8 GiB; 16 GiB is unverified for this load — check peak memory after the first runs and raise it (with more vCPU, which Cloud Run ties to memory) if a run exits 137. |
| `cgan-data-portal` | 1 vCPU | 512 MiB | — (Service) | Static file serving only (nginx on port 80, gen2 for GCS volumes). |

`--max-retries=1 --tasks=1 --parallelism=1` on every job matches `auto_forecasts.py`'s
single-process, sequential, idempotent-on-retry behavior — a retry just re-runs it, which
skips whatever already completed and exits non-zero only if a date/time in the range still
failed.

## Storage layout

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
(`--add-volume ... mount-options=only-dir=<prefix>`).

### Consumers of `interface/`

- **cgan-cms** (the public site, `../cgan-cms`) mounts `interface/{imerg,rfe,chirps}`
  read-only on its own Cloud Run service and serves them same-origin at `/data/`,
  `/data/rfe/`, `/data/chirps/`. Its `deploy/cloud_run_service.json` must name the same
  bucket as `_FORECAST_DATA_BUCKET` here. It no longer uses the old
  `icpac-data-portal…/cgan-data/` URL.
- **`cgan-data-portal`** (this repo's nginx image) serves the same three prefixes read-only at
  the same paths, with `Access-Control-Allow-Origin: *`, for any other consumer. It is
  data-only on Cloud Run: `/` returns 404, because `WEB_UPSTREAM` is unset there (in
  docker-compose it proxies `/` to the FastAPI `web` service, see
  `../configs/40-web-proxy.sh`).

The ELR climatology (`../ELR/climatological_exceedances`) is static repo data, not job output.
Both consumers expect it at `interface/imerg/staticELR_climate/`, so upload it once:

```bash
gcloud storage rsync ELR/climatological_exceedances gs://<bucket>/interface/imerg/staticELR_climate
```

## Before first deploy

Fill in / confirm:
- `_AR_DEPLOY_REGION` (default `europe-west1`) and `_AR_PROJECT_ID` (default: the build's project)
- `_FORECAST_DATA_BUCKET`: create the bucket (the prefixes above are created by the jobs on first
  write) and use the same name in cgan-cms' `deploy/cloud_run_service.json`
- The Artifact Registry repo `cgan` in `_AR_DEPLOY_REGION`
- The jobs' runtime service account needs `roles/storage.objectAdmin` on the bucket;
  cgan-cms' and the data portal's need `roles/storage.objectViewer`
- A service account for Cloud Scheduler with `roles/run.invoker` on each Cloud Run Job
  (`SCHEDULER_SA` in `setup-cloud-scheduler.sh`)
- `../datasets/imerg/cGAN_data/{elev.nc,lsm.nc}` are present in the repo (shared by all three
  datasets via `datasets/{chirps,rfe}/cGAN_data` symlinks) — no action needed.
- `RFE_climatology_meansd_doy.nc` is still missing from the repo (needed by `cgan-jobs-rfe-24h`'s
  `run11` field set, via `data.py`'s `climatology_channel()` reading `CONSTANTS_PATH`). Deploy
  that file into the shared `cGAN_data` constants before `cgan-jobs-rfe-24h`'s first real run —
  it will fail with a `FileNotFoundError` until then.
