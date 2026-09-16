# SEWAA-Forecasts (RFE2)

Welcome! This project provides operational rainfall forecasts for the ICPAC (IGAD Climate Prediction and Applications Centre) region in East Africa. The system uses advanced machine learning (cGAN - conditional Generative Adversarial Network) to generate accurate rainfall predictions. This deployment uses the **RFE2** cGAN (model **run13**).

## Table of Contents
- [SEWAA-Forecasts (RFE2)](#sewaa-forecasts-rfe2)
  - [Table of Contents](#table-of-contents)
  - [What is This Project?](#what-is-this-project)
  - [Installation Guide](#installation-guide)
    - [Step 1: Install Conda](#step-1-install-conda)
    - [Step 2: Download the Project](#step-2-download-the-project)
    - [Step 3: Set Up Python Environment](#step-3-set-up-python-environment)
    - [Step 4: Access ECMWF Data](#step-4-access-ecmwf-data)
    - [Method 1: Using Docker](#method-1-using-docker)
    - [Method 2: Using Python Directly](#method-2-using-python-directly)
  - [How to Use the Forecasts](#how-to-use-the-forecasts)
    - [Making a Single Forecast](#making-a-single-forecast)
    - [Automatic Forecasting](#automatic-forecasting)
    - [Using the API to Generate Forecasts](#using-the-api-to-generate-forecasts)
    - [Viewing Forecasts in the Web Interface](#viewing-forecasts-in-the-web-interface)
  - [Updating the Installation](#updating-the-installation)
  - [Troubleshooting](#troubleshooting)
  - [Getting Help](#getting-help)
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
- **24-hour rainfall accumulation forecasts** (RFE2 cGAN, model run13)
- **Interactive web interface** to view and explore forecasts
- **Multiple visualization options** including probability maps and rainfall values
- **Automated forecast generation** that runs on a schedule
- **Historical forecast data** for analysis and comparison

Before you begin, make sure you have:

1. **A computer** running Windows, macOS, or Linux
2. **Internet connection** for downloading data and dependencies
3. **At least 10 GB of free disk space**
4. **Basic familiarity with using the terminal/command line** (don't worry, we'll guide you through each step!)

**Optional but helpful:**
- Docker Desktop (for the easiest installation method)
- Git (for easier updates)

---

## Installation Guide

### Step 1: Install Conda

Conda is a package manager that helps organize Python and its dependencies. If you don't have it installed:

1. **Download Miniconda** (a lightweight version of Conda):
   - Go to: https://docs.conda.io/en/latest/miniconda.html
   - Download the installer for your operating system (Windows/Mac/Linux)
   - Run the installer and follow the on-screen instructions

2. **Verify the installation:**
   - Open a new terminal/command prompt window
   - Type: `conda --version`
   - You should see something like: `conda 23.x.x`

### Step 2: Download the Project

You have two options:

**Option A: Using the ZIP (recommended)**

1. Obtain `SEWAA-forecasts-RFE13.zip`
2. Extract it to a location you'll remember (e.g., `Documents` folder). On Windows, right-click → **Extract All**.
3. Open your terminal and navigate to the extracted folder:
   ```bash
   cd SEWAA-forecasts-RFE13
   ```

The ZIP already contains the model weights, the RFE2 climatology, the code, the interface, and a set of demo forecasts — so the interface works as soon as you start it.

**Option B: Using Git**

```bash
git lfs install                       # the climatology is a Git LFS file
git clone <your-repo-url>
cd SEWAA-forecasts-RFE13
git lfs pull                          # if the climatology came down as a tiny pointer
```

### Step 3: Set Up Python Environment

Now we'll create an isolated Python environment with all the necessary packages.

1. **Configure Conda channels** (these are sources for packages):
   ```bash
   conda config --add channels conda-forge
   conda config --set channel_priority strict
   ```

2. **Create a new environment named `tf215gpu`:**
   ```bash
   conda create -n tf215gpu python=3.11
   ```
   - When prompted with `Proceed ([y]/n)?`, type `y` and press Enter

3. **Activate the environment:**
   ```bash
   conda activate tf215gpu
   ```
   - You should see `(tf215gpu)` appear at the beginning of your terminal prompt

4. **Install all required packages** (this may take 15-30 minutes):
   ```bash
   pip install -r requirements.txt
   ```

5. **Verify TensorFlow installation:**
   ```bash
   python -c "import tensorflow as tf; print(tf.config.list_physical_devices('CPU'))"
   ```
   - You should see a list of CPU devices. If you see an error, something went wrong with the installation.

> If you already have the IMERG `tf215gpu` environment, you can reuse it — just run `pip install -r requirements.txt` to add anything missing.

### Step 4: Access ECMWF Data

The forecasts require meteorological data from ECMWF (European Centre for Medium-Range Weather Forecasts), downloaded automatically from the University of Oxford archive.

**Important:** Live operational data may require access to the ECMWF machine `gbmc`.

- **If you work with ICPAC or Oxford team:** Contact your supervisor for access.
- **If you're testing or developing:** The ZIP ships with demo forecast data, and past dates can be fetched from the Oxford archive.

---

### Method 1: Using Docker

Docker packages everything you need in a container, making it easier to run.

**Prerequisites:**
- Install Docker Desktop from: https://www.docker.com/products/docker-desktop

**Steps:**

1. **Navigate to the project directory:**
   ```bash
   cd SEWAA-forecasts-RFE13
   ```

2. **Build the Docker image** (first time only, takes 15-30 minutes):
   ```bash
   docker build -t sewaa-forecasts-rfe .
   ```

3. **Run the application:**
   ```bash
   docker run -p 8000:8000 -v $(pwd)/interface/data:/opt/cgan/interface/data sewaa-forecasts-rfe
   ```

4. **Access the web interface:**
   - Open your web browser
   - Go to: http://localhost:8000

### Method 2: Using Python Directly

If you prefer not to use Docker, you can run the application directly with Python.

1. **Navigate to the project directory:**
   ```bash
   cd SEWAA-forecasts-RFE13
   ```

2. **Activate your environment:**
   ```bash
   conda activate tf215gpu
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

1. **Activate your environment:**
   ```bash
   conda activate tf215gpu
   ```

2. **Navigate to the project directory:**
   ```bash
   cd SEWAA-forecasts-RFE13
   ```

3. **Run a basic forecast** (24h accumulation, most recent date):
   ```bash
   python run_forecast.py
   ```

4. **See all available options:**
   ```bash
   python run_forecast.py --help
   ```

**Advanced Usage Examples:**

- **Generate forecast for a specific date:**
  ```bash
  python run_forecast.py --date 20250117
  ```

- **Generate forecast without deleting intermediate files:**
  ```bash
  python run_forecast.py --delete_forecasts N
  ```

**What happens when you run a forecast:**
1. The script downloads ECMWF weather data from the Oxford archive
2. The cGAN model processes the data to generate rainfall predictions
3. The forecast data is processed and saved for visualization
4. The data is copied to the web interface directory

> This deployment is **24-hour only** (run13 is a 24h model), so `--accumulation` is `24h`.

### Automatic Forecasting

For operational use, you can run forecasts automatically on a schedule.

1. **Start the automatic forecasting script:**
   ```bash
   conda activate tf215gpu
   python start_forecasting.py
   ```

2. **What it does:**
   - Checks every 15 minutes for missing forecasts
   - Automatically generates any missing forecasts from the last 2 days
   - Keeps only the processed data (histogram data) for viewing
   - Deletes raw forecast files to save disk space

3. **Keep it running:**
   - The script runs continuously until you stop it
   - To stop: Press `Ctrl + C`
   - To run in background: Use `screen` or `tmux` (advanced)

### Using the API to Generate Forecasts

The application includes a REST API that allows you to generate forecasts programmatically.

1. **Start the web server** (Method 2 above)

2. **Open the interactive API documentation** in your browser:
   ```
   http://localhost:8000/docs
   ```

**Available Endpoints:**

- `/app-status` (GET) — Check if the application is running
- `/gen-forecast` (GET) — Generate cGAN forecasts with custom parameters

**`/gen-forecast` parameters:**

| Parameter | Type | Options | Default | Description |
|-----------|------|---------|---------|-------------|
| `accumulation` | string | `24h` | `24h` | Forecast accumulation period |
| `time` | string | `0000` | `0000` | Forecast initialization time (UTC) |
| `forecast_date` | string | `YYYYMMDD` | Today's date | Date to generate the forecast for |
| `delete_forecasts` | string | `Y` or `N` | `Y` | Delete raw forecast files after processing |

**Example (curl):**
```bash
curl -X GET "http://localhost:8000/gen-forecast?accumulation=24h&forecast_date=20250117"
```

The endpoint returns immediately after starting the forecast; the work happens in the background and may take several minutes. Check the terminal for progress, and the forecast appears in the web interface once complete.

### Viewing Forecasts in the Web Interface

1. **Make sure the web server is running**

2. **Open your browser and navigate to:**
   ```
   http://localhost:8000
   ```

3. **Navigate through the interface:**

   **Show Forecasts Page:**
   - **Model Selection:** 24h accumulation
   - **Region:** Select a specific country or view all East Africa
   - **Initialization Date & Time:** Choose when the forecast was made
   - **Valid Time:** Select which forecast time period to view
   - **Plot Type:** View probability maps or rainfall values
   - **Interactive Features:**
     - Click on the map to see local rainfall distribution
     - Use arrow keys to navigate by 0.1 degrees
     - Adjust rainfall thresholds and probability levels

   **Evaluation Tools:** CRPS Comparison, Categories of Reliability, Cost-Loss Ratios, and Ensemble Logistic Regression pages.

---

## Updating the Installation

**If You Use Git:**
```bash
cd SEWAA-forecasts-RFE13
git pull
```

**If You Downloaded as ZIP:**

1. Extract the new ZIP to a new location.
2. Copy your data from the old installation to the new one:

   **On macOS/Linux:**
   ```bash
   cp -r SEWAA-forecasts-RFE13-OLD/interface/data SEWAA-forecasts-RFE13-NEW/interface/
   cp -r SEWAA-forecasts-RFE13-OLD/24h_accumulations/IFS_forecast_data SEWAA-forecasts-RFE13-NEW/24h_accumulations/
   ```

   **On Windows:** Use File Explorer to copy `interface/data` and `24h_accumulations/IFS_forecast_data`.

---

## Troubleshooting

**1. "conda: command not found"**
   - Conda is not installed or not in your PATH. Reinstall Miniconda and restart your terminal.

**2. "ImportError: No module named 'tensorflow'" (or another package)**
   - The wrong environment is active, or a package is missing. Run `conda activate tf215gpu`, then `pip install -r requirements.txt`.

**3. "Port 8000 is already in use"**
   - Another app is using port 8000. Use another: `uvicorn main:app --port 8001`.

**4. Web page shows the wrong (IMERG) content**
   - Your browser cached a previous app on the same port. Hard-refresh with **Ctrl+Shift+R**, or use a private window.

**5. Forecasts not appearing in the web interface**
   - Check the data files exist: `ls -la interface/data/counts_24h`. If empty, run `python run_forecast.py`.

**6. "Cannot download data" / download is slow**
   - The Oxford archive throttles and sometimes drops connections; just re-run — `run_forecast.py` re-downloads an incomplete file automatically. A date's 00Z file may also not be published yet (~09:30 UTC).

**7. Forecast is very slow (~1 hour)**
   - You are running on CPU (native Windows has no TensorFlow GPU). This is expected; use a Linux/GPU host or WSL2 for speed.

**8. Docker build fails**
   - Check Docker Desktop is running and you have 10+ GB free. Try `docker system prune` to free space.

---

## Getting Help

**Resources:**
- cGAN paper: https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022MS003120
- ECMWF IFS: https://confluence.ecmwf.int/display/FUG
- RFE2 data: https://www.cpc.ncep.noaa.gov/products/fews/rfe.shtml

**Contact:**
- **ICPAC Team:** For operational forecasting and data access
- **Oxford Team:** For technical development and research questions

---

## Project Structure

```
SEWAA-forecasts-RFE13/
├── 24h_accumulations/         # 24-hour forecast data and models
├── interface/                 # Web interface files
│   ├── static/               # JavaScript, CSS, images
│   ├── data/                 # Forecast data for visualization
│   └── *.html                # Web pages
├── shapes/                    # Geographic boundary files
├── ELR/                       # Ensemble Logistic Regression code
├── cGAN_data/                # Constants and the RFE2 climatology
├── run_forecast.py           # Main forecast generation script
├── start_forecasting.py      # Automatic forecasting script
├── main.py                   # FastAPI web server
├── Dockerfile                # Docker configuration
└── README.md                 # This file
```

---

## License

This project is maintained by ICPAC-IGAD for operational rainfall forecasting in East Africa. Architecture and cGAN code adapted from Oxford's ARC cGAN.

---

**Version:** 3 (run13, RFE2)

---

**Happy Forecasting! 🌧️📊**

If you encounter any problems not covered in this README, please don't hesitate to reach out.
```
