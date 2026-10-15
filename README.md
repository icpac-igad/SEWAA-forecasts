# SEWAA-Forecasts

Welcome! This project provides operational rainfall forecasts for the ICPAC (IGAD Climate Prediction and Applications Centre) region in East Africa. The system uses advanced machine learning (cGAN - conditional Generative Adversarial Network) to generate accurate rainfall predictions.

## Table of Contents
- [SEWAA-Forecasts](#sewaa-forecasts)
  - [Table of Contents](#table-of-contents)
  - [What is This Project?](#what-is-this-project)
    - [Supported Datasets](#supported-datasets)
    - [Requirements](#requirements)
  - [Installation Guide](#installation-guide)
    - [Step 1: Download the Project](#step-1-download-the-project)
      - [Option A: Using Git (Recommended if you have Git installed)](#option-a-using-git-recommended-if-you-have-git-installed)
      - [Option B: Download as ZIP (For beginners)](#option-b-download-as-zip-for-beginners)
    - [Step 2: Set Up Python Environment](#step-2-set-up-python-environment)
      - [Option A: Using uv (Recommended — the same tool the Docker image uses)](#option-a-using-uv-recommended--the-same-tool-the-docker-image-uses)
      - [Option B: Using Conda](#option-b-using-conda)
      - [Verify the installation](#verify-the-installation)
    - [Step 3: IFS Forecast Data](#step-3-ifs-forecast-data)
  - [Running the Application](#running-the-application)
    - [Method 1: Using Docker (Recommended for Beginners)](#method-1-using-docker-recommended-for-beginners)
      - [Prerequisites:](#prerequisites)
      - [Steps:](#steps)
      - [Running the Full Stack with Docker Compose](#running-the-full-stack-with-docker-compose)
    - [Method 2: Using Python Directly](#method-2-using-python-directly)
  - [How to Use the Forecasts](#how-to-use-the-forecasts)
    - [Making a Single Forecast](#making-a-single-forecast)
    - [Automatic Forecasting](#automatic-forecasting)
    - [Using the API to Generate Forecasts](#using-the-api-to-generate-forecasts)
      - [Accessing the API Documentation](#accessing-the-api-documentation)
      - [Available API Endpoints](#available-api-endpoints)
      - [Using the `/gen-forecast` Endpoint](#using-the-gen-forecast-endpoint)
      - [How to Use the Interactive API Docs](#how-to-use-the-interactive-api-docs)
      - [Understanding the Response](#understanding-the-response)
      - [API Usage Examples for Different Scenarios](#api-usage-examples-for-different-scenarios)
      - [Setting Up Automated API Calls](#setting-up-automated-api-calls)
      - [Alternative API Documentation](#alternative-api-documentation)
    - [Viewing Forecasts in the Web Interface](#viewing-forecasts-in-the-web-interface)
  - [Updating the Installation](#updating-the-installation)
    - [If You Use Git:](#if-you-use-git)
    - [If You Downloaded as ZIP:](#if-you-downloaded-as-zip)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues and Solutions](#common-issues-and-solutions)
      - [1. **"conda: command not found" / "uv: command not found"**](#1-conda-command-not-found--uv-command-not-found)
      - [2. **"ImportError: No module named 'tensorflow'"**](#2-importerror-no-module-named-tensorflow)
      - [3. **"Port 8000 is already in use"**](#3-port-8000-is-already-in-use)
      - [4. **"Permission denied" errors**](#4-permission-denied-errors)
      - [5. **Forecasts not appearing in the web interface**](#5-forecasts-not-appearing-in-the-web-interface)
      - [6. **"Cannot download IFS data"**](#6-cannot-download-ifs-data)
      - [7. **Web page loads but shows no data**](#7-web-page-loads-but-shows-no-data)
      - [8. **Docker build fails**](#8-docker-build-fails)
      - [9. **Forecast job container keeps restarting / exits with code 137**](#9-forecast-job-container-keeps-restarting--exits-with-code-137)
  - [Getting Help](#getting-help)
    - [Resources](#resources)
    - [Contact](#contact)
    - [Contributing](#contributing)
  - [Project Structure](#project-structure)
  - [License](#license)

---

## What is This Project?

This application generates and visualizes rainfall forecasts for East African countries including:
- Burundi
- Djibouti
- Eritrea
- Ethiopia
- Kenya
- Rwanda
- Somalia
- South Sudan
- Sudan
- Tanzania
- Uganda

**Key Features:**
- **6-hour and 24-hour rainfall accumulation forecasts**
- **Interactive web interface** to view and explore forecasts
- **Multiple visualization options** including probability maps and rainfall values
- **Automated forecast generation** that runs on a schedule
- **Historical forecast data** for analysis and comparison

### Supported Datasets

The same code base produces forecasts from cGAN models trained against three different
rainfall datasets. Which one a script or container works on is chosen with the
`CGAN_DATASET` environment variable (see `dataset_config.py`):

| `CGAN_DATASET` | Dataset | Accumulations |
|----------------|---------|---------------|
| `imerg` (default) | IMERG | 6h and 24h |
| `chirps` | CHIRPS | 24h |
| `rfe` | RFE | 24h |

### Requirements

Before you begin, make sure you have:

1. **A computer** running Windows, macOS, or Linux
2. **Internet connection** for downloading data and dependencies
3. **At least 10 GB of free disk space** (plus up to 16 GB of RAM for operational runs,
   which generate 1000-member ensembles)
4. **Basic familiarity with using the terminal/command line** (don't worry, we'll guide you through each step!)

**Optional but helpful:**
- Docker Desktop (for the easiest installation method)
- Git (for easier updates)

---

## Installation Guide

### Step 1: Download the Project

You have two options:

#### Option A: Using Git (Recommended if you have Git installed)

```bash
# Navigate to where you want to store the project
cd ~/Documents

# Clone the repository
git clone https://github.com/icpac-igad/SEWAA-forecasts.git

# Enter the project directory
cd SEWAA-forecasts
```

#### Option B: Download as ZIP (For beginners)

1. Go to: https://github.com/icpac-igad/SEWAA-forecasts
2. Click the green **"<> Code"** button
3. Click **"Download ZIP"**
4. Extract the ZIP file to a location you'll remember (e.g., `Documents` folder)
5. Open your terminal and navigate to the extracted folder:
   ```bash
   cd ~/Documents/SEWAA-forecasts-main
   ```

### Step 2: Set Up Python Environment

> Skip this step if you only plan to run the project with Docker — the image installs
> everything for you.

The project needs **Python 3.11 or 3.12**. Its dependencies are listed in
`pyproject.toml` and pinned in `uv.lock`.

#### Option A: Using uv (Recommended — the same tool the Docker image uses)

1. **Install uv** (see https://docs.astral.sh/uv/getting-started/installation/):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Create the environment and install all packages** (this may take 15-30 minutes):
   ```bash
   uv sync
   ```

3. **Activate the environment:**
   ```bash
   source .venv/bin/activate        # macOS/Linux
   .venv\Scripts\activate           # Windows
   ```

#### Option B: Using Conda

1. **Install Miniconda** from https://docs.conda.io/en/latest/miniconda.html and verify
   it with `conda --version`.

2. **Create and activate a new environment named `tf215gpu`:**
   ```bash
   conda config --add channels conda-forge
   conda config --set channel_priority strict
   conda create -n tf215gpu python=3.11
   conda activate tf215gpu
   ```
   - You should see `(tf215gpu)` appear at the beginning of your terminal prompt

3. **Install all required packages** (this may take 15-30 minutes):
   ```bash
   pip install tensorflow==2.15.0 cartopy cfgrib climlab dask ecmwf-api-client "fastapi[standard]" flake8 iris jinja2 jupyter markdown2 matplotlib netcdf4 numba pre-commit properscoring regionmask ruff schedule scikit-learn seaborn tqdm xarray xesmf
   conda install conda-forge::curl
   ```

#### Verify the installation

```bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('CPU'))"
```
You should see a list of CPU devices. If you see an error, something went wrong with the installation.

### Step 3: IFS Forecast Data

The cGAN models are driven by ECMWF IFS forecasts. **No credentials are needed:**
`run_forecast.py` downloads the IFS initialization files it needs over HTTP from public
mirrors, trying each in turn (University of Oxford, megacorr.dynu.net, then the ICPAC data
portal). The machine only needs outbound internet access to those sites.

---

## Running the Application

### Method 1: Using Docker (Recommended for Beginners)

Docker packages everything you need in a container, making it easier to run.

#### Prerequisites:
- Install Docker Desktop from: https://www.docker.com/products/docker-desktop

#### Steps:

1. **Navigate to the project directory:**
   ```bash
   cd ~/Documents/SEWAA-forecasts
   ```

2. **Build the Docker image** (first time only, takes 15-30 minutes):
   ```bash
   docker build -t sewaa-forecasts .
   ```

3. **Run the application:**
   ```bash
   docker run -p 8000:8000 -e CGAN_DATASET=imerg -v $(pwd)/interface/data:/opt/cgan/interface/data sewaa-forecasts
   ```

4. **Access the web interface:**
   - Open your web browser
   - Go to: http://localhost:8000
   - You should see the SEWAA Forecasts homepage!

**Explanation of the Docker command:**
- `-p 8000:8000` - Makes the app accessible on port 8000
- `-e CGAN_DATASET=imerg` - Selects the dataset (`imerg`, `chirps` or `rfe`)
- `-v $(pwd)/interface/data:/opt/cgan/interface/data` - Shares the data folder so forecasts persist
- `sewaa-forecasts` - The name of the Docker image we built

The web server starts 4 workers by default; add `-e API_WORKERS=<n>` to change that.

#### Running the Full Stack with Docker Compose

For an operational (always-on) deployment, `docker-compose.yml` runs the web API, one
forecasting job per dataset, and the nginx data proxy together:

| Service  | Default container name | What it does |
|----------|------------------------|--------------|
| `web`    | `cgan-web`             | FastAPI web server (`CGAN_DATASET`, default `imerg`) |
| `imerg`  | `cgan-imerg-jobs`      | Runs `start_forecasting.py` for IMERG (6h + 24h) |
| `rfe`    | `cgan-rfe-jobs`        | Runs `start_forecasting.py` for RFE (24h) |
| `chirps` | `cgan-chirps-jobs`     | Runs `start_forecasting.py` for CHIRPS (24h) |
| `nginx`  | `cgan-proxy-server`    | Serves the forecast and counts data on ports 80/443 |

1. **Configure the environment** (optional — every setting has a default):
   ```bash
   cp .env.example .env
   ```
   Set `STORE` to a folder outside the repo (e.g. `/mnt/data/cgan`) so forecast data
   survives re-checkouts. Container names can be overridden with `WEB_CNTR_NAME`,
   `JOBS_CNTR_NAME` (imerg), `RFE_JOBS_CNTR_NAME`, `CHIRPS_JOBS_CNTR_NAME` and
   `NGINX_CNTR_NAME`.

2. **Build and start everything:**
   ```bash
   docker compose up -d --build
   ```

3. **Start or follow only some services:**
   ```bash
   docker compose up -d web imerg nginx    # IMERG only
   docker compose logs -f rfe              # follow the RFE job logs
   ```

**Resource settings:**
- `WEB_API_WORKERS` — number of FastAPI workers in the `web` container (default: `4`;
  the image's built-in default `API_WORKERS` is also `4`).
- `CGAN_MEM_LIMIT` / `CGAN_MEM_RESERVATION` — memory cap and soft reservation applied
  to `web` and every job service (default: `16g` / `4g`). The host running the jobs
  needs this much free memory, since inference runs `ensemble_members: 1000`.

> **Upgrading from an older compose file:** the job services were renamed
> (`jobs` → `imerg`, `jobs-rfe` → `rfe`, `jobs-chirps` → `chirps`) and the IMERG job
> container is now `cgan-imerg-jobs` (was `cgan-jobs`). Remove the old containers with
> `docker compose up -d --remove-orphans`, and update any scripts that reference the old
> names (e.g. `docker logs cgan-jobs`).

### Method 2: Using Python Directly

If you prefer not to use Docker, you can run the application directly with Python.

1. **Navigate to the project directory:**
   ```bash
   cd ~/Documents/SEWAA-forecasts
   ```

2. **Activate the environment you created in [Step 2](#step-2-set-up-python-environment):**
   ```bash
   source .venv/bin/activate     # uv
   conda activate tf215gpu       # or conda
   ```

3. **Start the web server:**
   ```bash
   fastapi run --port 8000
   ```

   **Alternative (if fastapi command not found):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Access the web interface:**
   - Open your browser and go to: http://localhost:8000

5. **To stop the server:**
   - Press `Ctrl + C` in the terminal

---

## How to Use the Forecasts

### Making a Single Forecast

To generate forecasts manually, use the `run_forecast.py` script.

1. **Activate your environment** (`source .venv/bin/activate` or `conda activate tf215gpu`)

2. **Navigate to the project directory:**
   ```bash
   cd ~/Documents/SEWAA-forecasts
   ```

3. **Run a basic forecast** (yesterday's UTC date, initialized at 00:00, using the
   dataset's default accumulation — 6h for IMERG, 24h for CHIRPS and RFE):
   ```bash
   python run_forecast.py
   ```
   Use `CGAN_DATASET` to pick the dataset (default `imerg`):
   ```bash
   CGAN_DATASET=chirps python run_forecast.py
   ```

4. **See all available options:**
   ```bash
   python run_forecast.py --help
   ```

**Advanced Usage Examples:**

- **Generate 24-hour accumulation forecast:**
  ```bash
  python run_forecast.py --accumulation 24h
  ```

- **Generate forecast for a specific date:**
  ```bash
  python run_forecast.py --date 20250117
  ```

- **Generate forecast for a specific initialization time** (6h forecasts only accept
  `0000`, `0600`, `1200` or `1800`; 24h forecasts are initialized at `0000` only):
  ```bash
  python run_forecast.py --accumulation 6h --time 1200
  ```

- **Generate forecast without deleting intermediate files:**
  ```bash
  python run_forecast.py --delete_forecasts N
  ```

- **Skip the Ensemble Logistic Regression (ELR) forecasts:**
  ```bash
  python run_forecast.py --disable_ELR
  ```

**What happens when you run a forecast:**
1. The script downloads the IFS (ECMWF) initialization data, trying each public mirror in
   turn (University of Oxford, megacorr.dynu.net, then the ICPAC data portal). Each file
   is downloaded to a temporary `*.part` file and only moved into place once it opens as
   valid netCDF, with up to 3 attempts per mirror — so an interrupted download is retried
   and never leaves a truncated file for the forecast step to read. An existing but
   corrupt IFS file, or a `*.part` file left by a killed download, is deleted
   automatically.
2. The cGAN model processes the data to generate rainfall predictions
3. The forecast data is processed and saved for visualization
4. The data is copied to the web interface directory

Forecasts that already have output are skipped, so re-running the same command is safe. A
forecast whose output file is incomplete (e.g. the process was killed part-way) is
detected and regenerated.

### Automatic Forecasting

For operational use, you can run forecasts automatically on a schedule.

1. **Start the automatic forecasting script** (for the dataset in `CGAN_DATASET`):
   ```bash
   python start_forecasting.py
   CGAN_DATASET=rfe python start_forecasting.py   # another dataset
   ```

2. **What it does:**
   - Checks every 15 minutes for missing forecasts (both 6h and 24h for IMERG, 24h for
     CHIRPS and RFE)
   - Automatically generates any missing forecasts from the last 2 days
   - Keeps only the processed data (histogram data) for viewing
   - Deletes raw forecast files to save disk space

3. **Keep it running:**
   - The script runs continuously until you stop it
   - To stop: Press `Ctrl + C`
   - To run in background: Use `screen` or `tmux` (advanced), or run the `imerg`, `rfe`
     and `chirps` services from [Docker Compose](#running-the-full-stack-with-docker-compose),
     which each run this script

**One-shot alternative:** `auto_forecasts.py` does the same catch-up for a single
dataset and accumulation, then exits — useful for cron or Cloud Run Jobs (see
`deploy/README.md`):
```bash
python auto_forecasts.py --dataset imerg --accumulation 6h
python auto_forecasts.py --dataset chirps --accumulation 24h --days_to_check 2
```

Runs of the same channel never overlap: a run that starts while another is still busy
exits straight away. The lock lives in the data bucket when `CGAN_LOCK_BUCKET` is set
(Cloud Run), otherwise it's a local file lock (`job_lock.py`).

### Using the API to Generate Forecasts

The application includes a REST API that allows you to generate forecasts programmatically. This is useful for automation, integration with other systems, or remote forecast generation.

#### Accessing the API Documentation

1. **Start the web server** (see [Running the Application](#running-the-application))

2. **Open the interactive API documentation** in your browser:
   ```
   http://localhost:8000/docs
   ```
   or
   ```
   http://127.0.0.1:8000/docs
   ```

3. **You'll see the Swagger UI interface** with all available API endpoints

#### Available API Endpoints

**1. Health Check Endpoint**
- **URL:** `/app-status`
- **Method:** GET
- **Purpose:** Check if the application is running
- **Response:** Returns the application status (online, offline, or maintenance)

**2. Generate Forecast Endpoint**
- **URL:** `/gen-forecast`
- **Method:** GET
- **Purpose:** Generate cGAN forecasts with custom parameters

#### Using the `/gen-forecast` Endpoint

This is the main endpoint for generating forecasts. It runs `run_forecast.py` for the
dataset the server was started with (`CGAN_DATASET`). It accepts several optional parameters:

**Parameters:**

| Parameter | Type | Options | Default | Description |
|-----------|------|---------|---------|-------------|
| `accumulation` | string | `6h` or `24h` | Dataset default (6h for IMERG, 24h for CHIRPS/RFE) | Forecast accumulation period |
| `time` | string | `0000`, `0600`, `1200`, `1800` | `0000` | Forecast initialization time (UTC) |
| `forecast_date` | string | `YYYYMMDD` format | Today's date (at request time) | Date for which to generate forecast |
| `delete_forecasts` | string | `Y` or `N` | `Y` | Delete raw forecast files after processing |

#### How to Use the Interactive API Docs

**Method 1: Using the Swagger UI (Beginner-Friendly)**

1. **Navigate to the API docs:**
   ```
   http://localhost:8000/docs
   ```

2. **Find the `/gen-forecast` endpoint** in the list

3. **Click on the endpoint** to expand it

4. **Click the "Try it out" button** (top right of the endpoint section)

5. **Fill in the parameters** (or leave them blank for defaults):
   - **accumulation:** Type `6h` or `24h` (or leave empty for the dataset's default)
   - **time:** Select `0000`, `0600`, `1200`, or `1800`
   - **forecast_date:** Enter a date like `20250117` (or leave empty for today)
   - **delete_forecasts:** Type `Y` or `N`

6. **Click the "Execute" button**

7. **View the response** in the "Responses" section below
   - You'll see the status of your forecast generation request
   - Typical response: `{"status": "started"}`

**Method 2: Using curl (Command Line)**

You can also call the API from the command line using `curl`:

**Basic forecast (default parameters):**
```bash
curl -X GET "http://localhost:8000/gen-forecast"
```

**6-hour accumulation forecast for today at 00:00 UTC:**
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=0000"
```

**24-hour accumulation forecast for a specific date:**
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=24h&forecast_date=20250117"
```

**Generate forecast for specific date and time, keep intermediate files:**
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=1200&forecast_date=20250117&delete_forecasts=N"
```

**Method 3: Using Python requests Library**

For integration with Python scripts:

```python
import requests

# Basic forecast
response = requests.get("http://localhost:8000/gen-forecast")
print(response.json())

# Advanced forecast with parameters
params = {
    "accumulation": "24h",
    "time": "0000",
    "forecast_date": "20250117",
    "delete_forecasts": "Y"
}
response = requests.get("http://localhost:8000/gen-forecast", params=params)
print(response.json())
```

**Method 4: Using JavaScript/Fetch**

For web applications:

```javascript
// Basic forecast
fetch('http://localhost:8000/gen-forecast')
  .then(response => response.json())
  .then(data => console.log(data));

// Advanced forecast with parameters
const params = new URLSearchParams({
  accumulation: '6h',
  time: '1200',
  forecast_date: '20250117',
  delete_forecasts: 'Y'
});

fetch(`http://localhost:8000/gen-forecast?${params}`)
  .then(response => response.json())
  .then(data => console.log(data));
```

#### Understanding the Response

When you call `/gen-forecast`, you'll receive a JSON response:

```json
{
  "status": "started"
}
```

The endpoint currently always returns `started` — it does not track the job afterwards
(the response schema also reserves `complete`, `pending` and `failed` for future use).

**Important Notes:**

⚠️ **The endpoint returns immediately** after starting the forecast generation process. The actual forecast generation happens in the background and may take several minutes to complete.

⚠️ **Check the terminal/logs** to see the progress of forecast generation
(`docker compose logs -f web` when running under Docker Compose).

⚠️ **The forecast will be available** in the web interface once processing is complete (check `http://localhost:8000/showForecasts.html`).

#### API Usage Examples for Different Scenarios

**Example 1: Daily Automated Forecast**
Generate today's forecast (dataset's default accumulation) initialized at midnight:
```bash
curl -X GET "http://localhost:8000/gen-forecast?time=0000"
```

**Example 2: Backfill Missing Forecast**
Generate a forecast for a specific past date:
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&forecast_date=20250115&time=1200"
```

**Example 3: Development/Testing**
Generate forecast and keep all intermediate files for debugging:
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&delete_forecasts=N"
```

**Example 4: Multiple Time Steps**
Generate forecasts for all time steps of the day (run separately):
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=0000"
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=0600"
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=1200"
curl -X GET "http://localhost:8000/gen-forecast?accumulation=6h&time=1800"
```

#### Setting Up Automated API Calls

**Using cron (Linux/Mac):**

Edit your crontab:
```bash
crontab -e
```

Add a line to run forecasts daily at 2 AM:
```bash
0 2 * * * curl -X GET "http://localhost:8000/gen-forecast" >> /var/log/sewaa-forecast.log 2>&1
```

**Using Windows Task Scheduler:**

1. Open Task Scheduler
2. Create a new task
3. Set the trigger (e.g., daily at 2:00 AM)
4. Set the action to run a PowerShell script:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/gen-forecast" -Method Get
   ```

#### Alternative API Documentation

You can also access the ReDoc-style documentation at:
```
http://localhost:8000/redoc
```

This provides a different view of the same API with a cleaner, more readable format.

### Viewing Forecasts in the Web Interface

1. **Make sure the web server is running** (see [Running the Application](#running-the-application))

2. **Open your browser and navigate to:**
   ```
   http://localhost:8000
   ```

3. **Navigate through the interface:**

   **Homepage:**
   - Overview of available forecast types
   - Quick links to different visualization pages

   **Show Forecasts Page:**
   - **Model Selection:** Choose between 6h or 24h accumulation
   - **Region:** Select a specific country or view all East Africa
   - **Initialization Date & Time:** Choose when the forecast was made
   - **Valid Time:** Select which forecast time period to view
   - **Plot Type:** View probability maps or rainfall values
   - **Interactive Features:**
     - Click on the map to see local rainfall distribution
     - Use arrow keys to navigate by 0.1 degrees
     - Adjust rainfall thresholds and probability levels

   **Ensemble Logistic Regression:**
   - Statistical analysis of forecast reliability
   - Compare different forecast models

   **Cost-Loss Ratios:**
   - Economic decision-making tools
   - Evaluate forecast value for different scenarios

   **Categories of Reliability:**
   - Forecast quality metrics
   - Reliability diagrams and statistics

---

## Updating the Installation

### If You Use Git:

```bash
cd ~/Documents/SEWAA-forecasts
git pull origin main
uv sync                                  # refresh Python packages (uv installs)
docker compose up -d --build --remove-orphans   # or rebuild the containers (Docker Compose)
```

### If You Downloaded as ZIP:

1. **Download the latest version** from: https://github.com/icpac-igad/SEWAA-forecasts
   - Click **"<> Code"** → **"Download ZIP"**

2. **Extract the new version** to a new location

3. **Copy your data** from the old installation to the new one:

   If you run via `docker-compose.yml` with `STORE` pointed at a folder **outside** the
   repo checkout (recommended — see `.env.example`), your data already lives outside
   both the OLD and NEW checkouts, so nothing needs copying: just point the new
   checkout's `STORE` at the same location.

   Only copy data if your old installation used the legacy repo-relative defaults
   (no `STORE` set, data under the checkout itself):

   **On macOS/Linux:**
   ```bash
   # Replace OLD and NEW with your actual folder names
   cp -r SEWAA-forecasts-OLD/store SEWAA-forecasts-NEW/store
   ```

   **On Windows:**
   - Use File Explorer to copy the `store` folder (contains `interface/` and
     `forecasts/`, each split by dataset: `imerg`, `rfe`, `chirps`) from the old
     checkout into the new one.

---

## Troubleshooting

### Common Issues and Solutions

#### 1. **"conda: command not found" / "uv: command not found"**
   - **Solution:** The tool is not installed or not in your PATH
   - Reinstall it ([Step 2](#step-2-set-up-python-environment)) and restart your terminal
   - For Miniconda, make sure to check the option to add Conda to PATH during installation

#### 2. **"ImportError: No module named 'tensorflow'"**
   - **Solution:** TensorFlow is not installed or the wrong environment is active
   - Run: `source .venv/bin/activate` (uv) or `conda activate tf215gpu` (conda)
   - If still failing: `uv sync`, or `pip install tensorflow==2.15.0`

#### 3. **"Port 8000 is already in use"**
   - **Solution:** Another application is using port 8000
   - Try a different port: `fastapi run --port 8001`
   - Or find and stop the process using port 8000

#### 4. **"Permission denied" errors**
   - **Solution:** You don't have write permissions
   - On macOS/Linux: Use `sudo` (but be careful!)
   - Or change the installation directory to one you own

#### 5. **Forecasts not appearing in the web interface**
   - **Solution:** Check if data files exist
   - Run: `ls -la ${STORE:-./store}/interface/imerg` (swap `imerg` for `rfe` or `chirps`
     if that's the dataset you're checking)
   - If empty, generate forecasts using `python run_forecast.py`

#### 6. **"Cannot download IFS data"**
   - The error `... is not available from any known source` means none of the IFS
     mirrors has that file yet — new initializations appear a few hours after the run
     time, so retry later or pick an earlier `--date`/`--time`
   - Check the server can reach the mirrors (e.g. `curl -I https://rain.physics.ox.ac.uk`)
   - Errors like `NetCDF: HDF error` came from reading half-downloaded files; current
     versions validate downloads and clean up stale `*.part` files, so just re-run

#### 7. **Web page loads but shows no data**
   - **Solution:** JavaScript files might not be loading
   - Check browser console for errors (F12 → Console tab)
   - Make sure `/static` directory exists and contains JS files

#### 8. **Docker build fails**
   - **Solution:** Check Docker Desktop is running
   - Ensure you have enough disk space (10+ GB free)
   - Try: `docker system prune` to free up space

#### 9. **Forecast job container keeps restarting / exits with code 137**
   - **Solution:** The container ran out of memory during inference
   - Make sure the host has at least `CGAN_MEM_LIMIT` (default `16g`) free, or raise it in `.env`
   - Run fewer job services at once (e.g. `docker compose up -d web imerg nginx`)

---

## Getting Help

### Resources

- **GitHub Issues:** https://github.com/icpac-igad/SEWAA-forecasts/issues
  - Search for similar problems
  - Create a new issue if you find a bug

- **Documentation:**
  - cGAN paper: https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022MS003120
  - ECMWF IFS: https://confluence.ecmwf.int/display/FUG
  - IMERG data: https://gpm.nasa.gov/data/imerg

### Contact

- **ICPAC Team:** For operational forecasting and data access
- **Oxford Team:** For technical development and research questions

### Contributing

Contributions are welcome! If you'd like to improve the code or documentation:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## Project Structure

```
SEWAA-forecasts/
├── 6h_accumulations/          # 6-hour forecast code, models and data (IMERG)
├── 24h_accumulations/         # 24-hour forecast code, models and data
├── datasets/                  # Per-dataset (imerg, chirps, rfe) model weights and configs
├── interface/                 # Web interface files
│   ├── static/               # JavaScript, CSS, images
│   ├── data/                 # Forecast data for visualization
│   └── *.html                # Web pages
├── shapes/                    # Geographic boundary files
├── ELR/                       # Ensemble Logistic Regression code
├── cGAN_data/                 # Model constants and normalisation data
├── configs/                   # nginx proxy configuration
├── deploy/                    # Cloud Run Jobs deployment (see deploy/README.md)
├── dataset_config.py          # Dataset registry, selected via CGAN_DATASET
├── run_forecast.py            # Main forecast generation script
├── start_forecasting.py       # Continuous automatic forecasting loop
├── auto_forecasts.py          # One-shot catch-up forecasting (cron / Cloud Run)
├── job_lock.py                # Per-channel lock so auto_forecasts.py runs never overlap
├── main.py                    # FastAPI web server
├── Dockerfile                 # Application image (web + forecast jobs)
├── nginx.Dockerfile           # Data proxy image
├── docker-compose.yml         # web, imerg, rfe, chirps and nginx services
├── .env.example               # Configuration template for docker-compose.yml
├── cloudbuild.yaml            # Cloud Build config for the Cloud Run Jobs
├── pyproject.toml / uv.lock   # Python dependencies
└── README.md                  # This file
```

---

## License

This project is maintained by ICPAC-IGAD for operational rainfall forecasting in East Africa.

---

**Last Updated:** October 2026

**Version:** 1.2.0

---

**Happy Forecasting! 🌧️📊**

If you encounter any problems not covered in this README, please don't hesitate to reach out or create an issue on GitHub. We're here to help!
