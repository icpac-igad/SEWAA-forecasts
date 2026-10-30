# SEWAA Forecasts

> **Research software.** The forecast models in this project are **experimental and under
> active research**. Their forecasts have not been fully validated and should not be used
> on their own to make decisions. For official forecasts, use your national meteorological
> service.

This project produces **experimental rainfall forecasts for East Africa**, covering the
ICPAC region: Burundi, Djibouti, Eritrea, Ethiopia, Kenya, Rwanda, Somalia, South Sudan,
Sudan, Tanzania and Uganda. It is developed by ICPAC and the University of Oxford as part
of the SEWAA project.

It takes the global weather forecast from ECMWF (called **IFS**) and refines it for East
Africa using a research machine-learning model (a **cGAN**). The result is a set of maps
of how likely rain is across the region for the next few days, which you can explore in
your web browser.

## Contents

- [Words used in this guide](#words-used-in-this-guide)
- [Easy setup with Docker (recommended for beginners)](#easy-setup-with-docker)
- [Advanced setup with Python](#advanced-setup-with-python)
  - [Install](#install)
  - [Make forecasts](#make-forecasts)
  - [View the forecasts](#view-the-forecasts)
- [Using the forecast page](#using-the-forecast-page)
- [Where your data is saved](#where-your-data-is-saved)
- [Asking the web server to make a forecast](#asking-the-web-server-to-make-a-forecast)
- [Updating to a newer version](#updating-to-a-newer-version)
- [Troubleshooting](#troubleshooting)
- [What's in this folder](#whats-in-this-folder)
- [More information](#more-information)

---

## Words used in this guide

| Word | Meaning |
|------|---------|
| **Dataset** | Which rainfall observations the model learned from: **IMERG** (satellite), **CHIRPS** or **RFE**. Each gives a slightly different forecast. |
| **Accumulation** | How much rain is added up in each map: **6h** (per 6 hours) or **24h** (per day). IMERG has both; CHIRPS and RFE are 24h only. |
| **Initialisation time** | When the weather forecast started (in UTC). 24h forecasts start at `0000`; 6h forecasts can start at `0000`, `0600`, `1200` or `1800`. |
| **Store** | The one folder where all the forecast data is saved. By default this is the `store` folder in this project. |

Which setup should I use?

- **New to this, or just want to see forecasts?** Use [Docker](#easy-setup-with-docker).
  You only install one program, run a few commands, and forecasts are made for you
  automatically.
- **Developing the code, or need to choose exactly which forecasts are made?** Use the
  [Python setup](#advanced-setup-with-python).

---

## Easy setup with Docker

Docker runs the whole system for you in the background: it makes new forecasts
automatically and serves the website. You don't need to install Python or anything else.

### What you need

- A computer with **at least 16 GB of memory (RAM)** and about **20 GB of free disk space**
- An internet connection. The forecast input data is downloaded automatically, and no
  account or password is needed.

### Steps

1. **Install Docker Desktop** from https://www.docker.com/products/docker-desktop and start it.
   In Docker Desktop, open **Settings → Resources** and give it as much memory as you can
   spare (16 GB or more).

2. **Download this project.** Open https://github.com/icpac-igad/SEWAA-forecasts, click the
   green **Code** button, then **Download ZIP**, and unzip it. (If you use Git:
   `git clone https://github.com/icpac-igad/SEWAA-forecasts.git`.)

3. **Open a terminal in the project folder** (macOS: *Terminal*; Windows: *PowerShell*;
   then type `cd ` followed by the folder's path).

4. **Start the website and IMERG forecasts:**
   ```bash
   docker compose up -d --build web imerg nginx
   ```
   The first time, this takes 15–30 minutes to set things up. After that it starts in
   seconds.

5. **Open http://localhost** in your browser and click through to the forecasts.

The system now checks for new weather data every 15 minutes and makes any forecasts that
are missing from the last 2 days. Making forecasts is slow, so the first ones can take a
while to appear. You can watch progress with:

```bash
docker compose logs -f imerg
```

### Everyday commands

```bash
docker compose up -d web imerg nginx        # start (after a restart, for example)
docker compose down                          # stop everything
docker compose logs -f imerg                 # watch IMERG forecasts being made
```

### Adding RFE and CHIRPS forecasts

Each dataset has its own forecasting service: `imerg`, `rfe` and `chirps`. Every one of
them needs a lot of memory, so start with IMERG and add the others only if your computer
can handle it:

```bash
docker compose up -d rfe chirps              # add RFE and CHIRPS
docker compose up -d --build                 # or: start everything at once
```

### Optional settings

To change settings, such as where data is saved, copy the settings file and edit it:

```bash
cp .env.example .env
```

The most useful settings are:

- **`STORE`:** where forecasts are saved (e.g. a larger disk). See
  [Where your data is saved](#where-your-data-is-saved).
- **`CGAN_MEM_LIMIT`:** the memory limit for each service (default `16g`).

For running on Google Cloud (Cloud Run Jobs), see [deploy/README.md](deploy/README.md).

---

## Advanced setup with Python

Run the project directly on your computer. Use this to develop the code, to make specific
forecasts by hand, or to run without Docker.

### Install

You need a computer with Linux, macOS or Windows, 16 GB of RAM and about 10 GB of free
disk space, plus a terminal.

1. **Download the code:**
   ```bash
   git clone https://github.com/icpac-igad/SEWAA-forecasts.git
   cd SEWAA-forecasts
   ```
   Every command below is run **from inside this project folder**.

2. **Install uv**, a tool that installs the right Python version and all the packages the
   project needs (see https://docs.astral.sh/uv/getting-started/installation/ for Windows):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Close and reopen the terminal afterwards.

3. **Install the project** (15–30 minutes the first time):
   ```bash
   uv sync
   ```

4. **Activate the environment.** Do this every time you open a new terminal:
   ```bash
   source .venv/bin/activate        # macOS / Linux
   .venv\Scripts\activate           # Windows
   ```
   Your prompt now starts with `(.venv)`.

5. **Check it works:**
   ```bash
   python -c "import tensorflow as tf; print('OK', tf.__version__)"
   ```

> Prefer conda? Create an environment with Python 3.11 (`conda create -n cgan python=3.11`),
> activate it, and run `pip install -e .` in the project folder.

### Make forecasts

**Catch up on recent days (recommended):**

```bash
python auto_forecasts.py --dataset imerg --accumulation 24h
```

This makes every forecast missing from the last 2 days, then stops. Forecasts that already
exist are skipped, so running it again is safe. More examples:

```bash
python auto_forecasts.py --dataset rfe --accumulation 24h       # RFE
python auto_forecasts.py --dataset chirps --accumulation 24h    # CHIRPS
python auto_forecasts.py --dataset imerg --accumulation 6h      # IMERG, every 6 hours

python auto_forecasts.py --dataset imerg --accumulation 24h --days_to_check 7    # last 7 days
python auto_forecasts.py --dataset imerg --accumulation 24h \
    --start_date 20261020 --final_date 20261025                                  # a date range
```

**One single forecast:**

```bash
python run_forecast.py --accumulation 24h --date 20261029
CGAN_DATASET=rfe python run_forecast.py --date 20261029           # another dataset
```

| Option | What it does |
|--------|--------------|
| `--date YYYYMMDD` | The day the forecast starts (default: yesterday) |
| `--accumulation 6h` or `24h` | 6-hourly or daily rain |
| `--time 1200` | Start time, for 6h forecasts (`0000`, `0600`, `1200`, `1800`) |
| `--delete_forecasts Y` | Delete the large raw files afterwards and keep only what the maps need |
| `--disable_ELR` | Skip the extra regional (ELR) forecasts for Kenya, Ethiopia and Rwanda |

See `python run_forecast.py --help` for all options.

**Keep forecasting automatically** (this is what the Docker services run):

```bash
python start_forecasting.py                      # IMERG (6h and 24h)
CGAN_DATASET=rfe python start_forecasting.py     # RFE
```

It checks every 15 minutes and makes any missing forecasts, until you stop it with `Ctrl + C`.

**What happens during a forecast.** Each output line starts with the dataset name, e.g.
`[IMERG]` or `[RFE]`. A forecast:

1. Downloads the input weather forecast (IFS), if it isn't saved yet, trying three mirror
   websites in turn. New forecasts are published about 8–10 hours after their start time,
   so very recent dates are skipped until then.
2. Runs the model to produce 1000 possible versions of the forecast (an "ensemble"). This
   is the slow part, and it needs a lot of memory.
3. Turns the result into map data for the website, and updates the list of available dates.

A forecast that was interrupted (for example, the computer ran out of memory) is detected
and made again on the next run.

### View the forecasts

There are two ways to view forecasts. Both read from your
[store](#where-your-data-is-saved) and show IMERG, RFE and CHIRPS.

**Option 1: the full website (`fastapi dev`).** This is the same website used in
production:

```bash
fastapi dev
```

Open **http://localhost:8000** and click through to the forecasts (or go straight to
http://localhost:8000/showForecasts.html).

- `fastapi dev` restarts itself when you change the code. For a server that stays up, use
  `fastapi run --port 8000` instead.
- If your store isn't the default `./store` folder, give the server the same setting:
  `STORE=/mnt/data/cgan fastapi dev`.

**Option 2: a simple file viewer (`python -m http.server`).** This needs nothing beyond
Python, so it's handy for a quick look:

```bash
python -m http.server 8000
```

Open **http://localhost:8000** and click **View forecasts**. The same page also links to the
raw data folders.

- This viewer always reads the `store` folder inside the project. If your data is
  somewhere else, link it once: `ln -s /mnt/data/cgan store` (macOS/Linux).
- Both options use port 8000, so run only one at a time, or give one another port
  (e.g. `python -m http.server 8080`).

---

## Using the forecast page

Open the forecast page:

| Setup | Address |
|-------|---------|
| Docker | http://localhost/showForecasts.html |
| `fastapi dev` | http://localhost:8000/showForecasts.html |
| `python -m http.server` | http://localhost:8000, then **View forecasts** |

> Remember that these are **experimental** forecasts (see the note at the top of this page).

### Your first map in four steps

1. **Pick the forecast.** Set **Accumulation Period** to *24-hour* (rain per day; the easiest
   to start with) and **Reference Dataset** to *IMERG*, *RFE* or *CHIRPS*.
2. **Pick the date.** Under **Initialization Date & Time**, choose the day the forecast
   starts. **Valid Time** picks which day (or 6-hour period) of that forecast to show.
3. **Pick the area.** Choose your country under **Region**, or keep *East Africa*. For some
   countries an **Admin 1** menu appears so you can zoom to a province or county.
4. **Read the map.** By default, the colours show the **chance of rain above an amount**
   (the *Value Threshold*). Tick **Show plot explanation** below the maps for a
   plain-language description of what you're looking at.

**Tip:** click anywhere on the map to see a chart (a *histogram*) of all the rainfall
amounts the model thinks are possible at that spot. Use the arrow keys to move the point
around, and **Remove histograms** to hide the charts.

### Which plot type should I use?

| Plot Type | Answers the question | Good for |
|-----------|----------------------|----------|
| **Probability to exceed value** (default) | "How likely is more than *X* mm of rain?" Set *X* in **Value Threshold**. | Most users; e.g. the chance of heavy rain above 20 mm/day |
| **Values below probability** | "How much rain could fall?" Set the **Probability Threshold**: *50%* gives a typical amount, *95%* a high amount that only 5% of the forecasts go above. | Planning for a likely or worst-case amount |
| **Ensemble mean** | The average of all forecast versions | Technical users. It can mislead for rainfall; *Values below probability* at 50% is usually better. |
| **Ensemble standard deviation** | How much the forecast versions disagree | Technical users. *Values below probability* at 95% is usually a clearer guide. |

### All the controls

| Control | What it does |
|---------|--------------|
| **Accumulation Period** | Rain per 6 hours or per day. RFE and CHIRPS are daily only; picking one switches to 24-hour. |
| **Forecast Model** | The input weather forecast. This project makes forecasts from **ECMWF IFS**, so leave it on that. |
| **Reference Dataset** | Which rainfall observations the model learned from (IMERG, RFE or CHIRPS) |
| **Region** / **Admin 1** | The area shown on the map |
| **Initialization Date & Time** | When the forecast started (UTC). Only dates that have forecasts are listed. |
| **Valid Time** | Which part of the forecast to show, or all of them side by side |
| **Style** | Colour scheme, including those used by ICPAC, the Kenya Meteorological Department (KMD), the Ethiopian Meteorological Institute (EMI) and ECMWF |
| **Plot Type** | What the colours mean (see the table above) |
| **Value Threshold** / **Units** | The rainfall amount used by *Probability to exceed value*, in mm/h, mm/6h or mm/day |
| **Probability Threshold** | The percentage used by *Values below probability* |
| **Display Format** | Show chances as percentages or as words ("Very low", "Low", "Medium", "High") |

### For technical users

- Each forecast is an ensemble of **1000 members**. The page doesn't load them directly.
  It reads per-pixel **histogram counts** (`counts_<YYYYMMDD>_<HH>_<lead>h.nc`) and the list
  of available dates (`available_dates.json`) from the store's `interface/<dataset>/counts_6h`
  and `counts_24h` folders.
- The website serves these under `/data/` (IMERG) and `/data/rfe/`, `/data/chirps/`. The
  simple file viewer reads `/store/interface/<dataset>/` directly.
- The page's code is in `interface/static/js/` (website) and `interface/view_forecasts/`
  (file viewer); the two copies of `testScript.js` are kept identical.

If the page says **"No ... forecasts available"**, no forecast has been made yet for that
dataset, accumulation and date. See [Troubleshooting](#troubleshooting).

---

## Where your data is saved

Everything (downloaded input, forecasts and the website's map data) goes into **one
folder, the store**. By default that's `store/` inside the project.

To use another location, such as a bigger disk:

- **With Docker:** set `STORE=/path/to/folder` in `.env`.
- **With Python:** run `export STORE=/path/to/folder` (macOS/Linux) in the terminal before
  your commands.

Inside the store:

```
store/
├── forecasts/
│   ├── IFS_6h_forecast_data/       # downloaded input (shared by all datasets)
│   ├── IFS_24h_forecast_data/
│   ├── imerg/6h/cGAN_forecasts/    # raw model output, per dataset
│   ├── imerg/24h/cGAN_forecasts/
│   ├── rfe/24h/cGAN_forecasts/
│   └── chirps/24h/cGAN_forecasts/
└── interface/
    ├── imerg/                      # what the website shows, per dataset
    ├── rfe/
    └── chirps/
```

Docker and the Python setup use the same layout, so you can switch between them without
moving data.

---

## Asking the web server to make a forecast

While the full website is running, you can start a forecast from your browser:

1. Open http://localhost:8000/docs (with Docker: http://localhost/docs)
2. Click **/gen-forecast**, then **Try it out**
3. Fill in the date and options (or leave them empty for today), then click **Execute**

Or from the terminal:

```bash
curl "http://localhost:8000/gen-forecast?accumulation=24h&forecast_date=20261029"
```

| Parameter | Values | Default |
|-----------|--------|---------|
| `accumulation` | `6h`, `24h` | the dataset's default |
| `forecast_date` | `YYYYMMDD` | today |
| `time` | `0000`, `0600`, `1200`, `1800` | `0000` |
| `delete_forecasts` | `Y`, `N` | `Y` |

The reply `{"status": "started"}` means the forecast has started. It finishes in the
background a few minutes later; watch the server's terminal (or `docker compose logs -f web`)
for progress. The server makes forecasts for the dataset it was started with
(`CGAN_DATASET`, default `imerg`).

---

## Updating to a newer version

```bash
git pull
uv sync                                          # if you run the project directly
docker compose up -d --build --remove-orphans    # if you use Docker
```

Your forecasts are in the store, so they're kept. If you downloaded a ZIP instead, download
the new one and copy your old `store` folder into it (or set `STORE` to the same place).

---

## Troubleshooting

**Docker: the forecast service keeps restarting**
It is running out of memory. Give Docker Desktop more memory (**Settings → Resources**), and
run only one forecast service (`docker compose up -d web imerg nginx`).

**"command not found" for `uv`, `python` or `fastapi`**
Close and reopen the terminal, go to the project folder, and activate the environment
again (`source .venv/bin/activate`).

**`No module named 'tensorflow'` (or any other module)**
The environment isn't active. Run `source .venv/bin/activate`, and `uv sync` if it still fails.

**"is not available from any known source"**
The input weather forecast for that date isn't published yet (it takes about 8–10 hours),
or the computer can't reach the internet. Try an earlier date, or try again later.

**The forecast stops with "Killed" or exit code 137**
The computer ran out of memory. Close other programs, make one forecast at a time, or use
a machine with more RAM.

**The website shows no forecasts**
- Check that forecasts exist: `ls store/interface/imerg/counts_24h` (or `rfe`, `chirps`).
  If it's empty, make some forecasts ([Docker](#easy-setup-with-docker) or [Python](#make-forecasts)).
- Check the website is reading the right store (see the `STORE` notes in
  [View the forecasts](#view-the-forecasts)).
- Try a different date, accumulation or dataset on the forecast page.
- Reload the page with `Ctrl + Shift + R` to bypass old cached files.

**"Address already in use" / port 8000 is busy**
Another server is already running on that port. Stop it with `Ctrl + C` in its terminal, or
use another port: `fastapi dev --port 8001` or `python -m http.server 8001`.

**Another run is in progress; exiting**
`auto_forecasts.py` won't run twice at the same time for the same dataset and accumulation.
Wait for the first run to finish.

Still stuck? Open an issue at https://github.com/icpac-igad/SEWAA-forecasts/issues and
include the error message.

---

## What's in this folder

```
SEWAA-forecasts/
├── auto_forecasts.py        # Make missing forecasts for a range of days, then stop
├── run_forecast.py          # Make one forecast
├── start_forecasting.py     # Keep making forecasts automatically
├── main.py                  # The website (FastAPI)
├── index.html               # Home page for `python -m http.server`
├── dataset_config.py        # Settings for each dataset (IMERG, CHIRPS, RFE)
├── job_lock.py              # Stops two identical runs at once
├── 6h_accumulations/        # 6-hour model and scripts
├── 24h_accumulations/       # 24-hour model and scripts
├── datasets/                # Per-dataset model settings and files
├── ELR/                     # Regional forecasts for Kenya, Ethiopia and Rwanda
├── interface/               # Website pages, scripts and map boundaries
├── shapes/                  # Country and county boundaries
├── store/                   # Your data (see "Where your data is saved")
├── configs/                 # Web server (nginx) settings for Docker
├── deploy/                  # Google Cloud deployment
├── Dockerfile, nginx.Dockerfile, docker-compose.yml, .env.example   # Docker setup
├── cloudbuild.yaml          # Google Cloud build
└── pyproject.toml, uv.lock  # Python packages
```

---

## More information

- The cGAN method: Harris et al. (2022), *A generative deep learning approach to stochastic
  downscaling of precipitation forecasts*, https://doi.org/10.1029/2022MS003120
- ECMWF IFS forecasts: https://www.ecmwf.int/
- Rainfall datasets: [IMERG](https://gpm.nasa.gov/data/imerg),
  [CHIRPS](https://www.chc.ucsb.edu/data/chirps),
  [RFE](https://www.cpc.ncep.noaa.gov/products/international/data.shtml)
- ICPAC forecasts website: https://cgan.icpac.net/

Maintained by ICPAC-IGAD. The models are experimental research models; see the note at the
top of this page.
