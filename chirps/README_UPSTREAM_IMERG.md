# SEWAA-Forecasts

Welcome! This project provides operational rainfall forecasts for the ICPAC (IGAD Climate Prediction and Applications Centre) region in East Africa. The system uses advanced machine learning (cGAN - conditional Generative Adversarial Network) to generate accurate rainfall predictions.

## Table of Contents
- [SEWAA-Forecasts](#sewaa-forecasts)
  - [Table of Contents](#table-of-contents)
  - [What is This Project?](#what-is-this-project)
  - [Installation Guide](#installation-guide)
    - [Step 1: Install Conda](#step-1-install-conda)
    - [Step 2: Download the Project](#step-2-download-the-project)
      - [Option A: Using Git (Recommended if you have Git installed)](#option-a-using-git-recommended-if-you-have-git-installed)
      - [Option B: Download as ZIP (For beginners)](#option-b-download-as-zip-for-beginners)
    - [Step 3: Set Up Python Environment](#step-3-set-up-python-environment)
    - [Step 4: Access ECMWF Data](#step-4-access-ecmwf-data)
    - [Method 1: Using Docker (Recommended for Beginners)](#method-1-using-docker-recommended-for-beginners)
      - [Prerequisites:](#prerequisites)
      - [Steps:](#steps)
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
      - [1. **"conda: command not found"**](#1-conda-command-not-found)
      - [2. **"ImportError: No module named 'tensorflow'"**](#2-importerror-no-module-named-tensorflow)
      - [3. **"Port 8000 is already in use"**](#3-port-8000-is-already-in-use)
      - [4. **"Permission denied" errors**](#4-permission-denied-errors)
      - [5. **Forecasts not appearing in the web interface**](#5-forecasts-not-appearing-in-the-web-interface)
      - [6. **"Cannot download ECMWF data"**](#6-cannot-download-ecmwf-data)
      - [7. **Web page loads but shows no data**](#7-web-page-loads-but-shows-no-data)
      - [8. **Docker build fails**](#8-docker-build-fails)
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

---

	conda config --add channels conda-forge
	conda config --set channel_priority strict
	conda create -n tf215gpu python=3.11
	conda activate tf215gpu
	python -m pip install tensorflow==2.15
	pip install numba
	pip install matplotlib
	pip install seaborn
	pip install cartopy
	pip install jupyter
	pip install xarray
	pip install netcdf4
	pip install scikit-learn
	pip install cfgrib
	pip install dask
	pip install tqdm
	pip install properscoring
	pip install climlab
	pip install iris
	pip install ecmwf-api-client
	pip install xesmf
	pip install flake8
	pip install regionmask
	pip install schedule
	conda install conda-forge::curl

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
   pip install tensorflow==2.15.0 numba matplotlib seaborn cartopy jupyter xarray netcdf4 scikit-learn cfgrib dask tqdm properscoring climlab iris regionmask ecmwf-api-client xesmf flake8 "fastapi[standard]" jinja2 pre-commit ruff
   ```
5. **Verify TensorFlow installation:**
   ```bash
   python -c "import tensorflow as tf; print(tf.config.list_physical_devices('CPU'))"
   ```
   - You should see a list of CPU devices. If you see an error, something went wrong with the installation.

### Step 4: Access ECMWF Data

The forecasts require meteorological data from ECMWF (European Centre for Medium-Range Weather Forecasts).

**Important:** You need special access credentials to download ECMWF data.

- **If you work with ICPAC or Oxford team:** Contact your supervisor for access to the ECMWF machine `gbmc`
- **If you're testing or developing:** You can use existing sample data or contact the project maintainers

---

	python -m http.server 8080
   
Then in a browser window go to the address

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
   docker run -p 8000:8000 -v $(pwd)/interface/data:/opt/cgan/interface/data sewaa-forecasts
   ```

4. **Access the web interface:**
   - Open your web browser
   - Go to: http://localhost:8000
   - You should see the SEWAA Forecasts homepage!

**Explanation of the Docker command:**
- `-p 8000:8000` - Makes the app accessible on port 8000
- `-v $(pwd)/interface/data:/opt/cgan/interface/data` - Shares the data folder so forecasts persist
- `sewaa-forecasts` - The name of the Docker image we built

### Method 2: Using Python Directly

If you prefer not to use Docker, you can run the application directly with Python.

1. **Navigate to the project directory:**
   ```bash
   cd ~/Documents/SEWAA-forecasts
   ```

2. **Create virtual enironment using python-venv, uv, conda or any other tool you prefer:**
   ```bash
   conda activate tf215gpu
   ```

3. **Activate your virtual environment:**
   ```bash
   conda activate tf215gpu
   ```

4. **Start the web server:**
   ```bash
   fastapi run --port 8000
   ```

   **Alternative (if fastapi command not found):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

5. **Access the web interface:**
   - Open your browser and go to: http://localhost:8000

6. **To stop the server:**
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
   cd ~/Documents/SEWAA-forecasts
   ```

3. **Run a basic forecast** (generates 6h accumulation for today):
   ```bash
   python run_forecast.py
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

- **Generate forecast for a specific time:**
  ```bash
  python run_forecast.py --time 1200
  ```

- **Generate forecast without deleting intermediate files:**
  ```bash
  python run_forecast.py --delete_forecasts N
  ```

**What happens when you run a forecast:**
1. The script downloads ECMWF weather data from `gbmc` server
2. The cGAN model processes the data to generate rainfall predictions
3. The forecast data is processed and saved for visualization
4. The data is copied to the web interface directory

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

This is the main endpoint for generating forecasts. It accepts several optional parameters:

**Parameters:**

| Parameter | Type | Options | Default | Description |
|-----------|------|---------|---------|-------------|
| `accumulation` | string | `6h` or `24h` | None (both) | Forecast accumulation period |
| `time` | string | `0000`, `0600`, `1200`, `1800` | `0000` | Forecast initialization time (UTC) |
| `forecast_date` | string | `YYYYMMDD` format | Today's date | Date for which to generate forecast |
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
   - **accumulation:** Type `6h` or `24h` (or leave empty for both)
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

**Possible status values:**
- `started` - Forecast generation has begun
- `complete` - Forecast generation finished successfully
- `pending` - Forecast is queued but not yet started
- `failed` - Forecast generation encountered an error

**Important Notes:**

⚠️ **The endpoint returns immediately** after starting the forecast generation process. The actual forecast generation happens in the background and may take several minutes to complete.

⚠️ **Check the terminal/logs** to see the progress of forecast generation.

⚠️ **The forecast will be available** in the web interface once processing is complete (check `http://localhost:8000/showForecasts.html`).

#### API Usage Examples for Different Scenarios

**Example 1: Daily Automated Forecast**
Generate both 6h and 24h forecasts for today at midnight:
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
```

### If You Downloaded as ZIP:

1. **Download the latest version** from: https://github.com/icpac-igad/SEWAA-forecasts
   - Click **"<> Code"** → **"Download ZIP"**

2. **Extract the new version** to a new location

3. **Copy your data** from the old installation to the new one:

   **On macOS/Linux:**
   ```bash
   # Replace OLD and NEW with your actual folder names
   cp -r SEWAA-forecasts-OLD/interface/data SEWAA-forecasts-NEW/interface/
   cp -r SEWAA-forecasts-OLD/6h_accumulations/IFS_forecast_data SEWAA-forecasts-NEW/6h_accumulations/
   cp -r SEWAA-forecasts-OLD/6h_accumulations/cGAN_forecasts SEWAA-forecasts-NEW/6h_accumulations/
   cp -r SEWAA-forecasts-OLD/24h_accumulations/IFS_forecast_data SEWAA-forecasts-NEW/24h_accumulations/
   cp -r SEWAA-forecasts-OLD/24h_accumulations/cGAN_forecasts SEWAA-forecasts-NEW/24h_accumulations/
   ```

   **On Windows:**
   - Use File Explorer to copy these folders manually:
     - `interface/data`
     - `6h_accumulations/IFS_forecast_data`
     - `6h_accumulations/cGAN_forecasts`
     - `24h_accumulations/IFS_forecast_data`
     - `24h_accumulations/cGAN_forecasts`

---

## Troubleshooting

### Common Issues and Solutions

#### 1. **"conda: command not found"**
   - **Solution:** Conda is not installed or not in your PATH
   - Reinstall Miniconda and restart your terminal
   - Make sure to check the option to add Conda to PATH during installation

#### 2. **"ImportError: No module named 'tensorflow'"**
   - **Solution:** TensorFlow is not installed or the wrong environment is active
   - Run: `conda activate tf215gpu`
   - If still failing: `pip install tensorflow==2.15`

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
   - Run: `ls -la interface/data`
   - If empty, generate forecasts using `python run_forecast.py`

#### 6. **"Cannot download ECMWF data"**
   - **Solution:** You need access credentials
   - Contact ICPAC or Oxford team for `gbmc` access
   - Or use existing sample data for testing

#### 7. **Web page loads but shows no data**
   - **Solution:** JavaScript files might not be loading
   - Check browser console for errors (F12 → Console tab)
   - Make sure `/static` directory exists and contains JS files

#### 8. **Docker build fails**
   - **Solution:** Check Docker Desktop is running
   - Ensure you have enough disk space (10+ GB free)
   - Try: `docker system prune` to free up space

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
├── 6h_accumulations/          # 6-hour forecast data and models
├── 24h_accumulations/         # 24-hour forecast data and models
├── interface/                 # Web interface files
│   ├── static/               # JavaScript, CSS, images
│   ├── data/                 # Forecast data for visualization
│   └── *.html                # Web pages
├── shapes/                    # Geographic boundary files
├── ELR/                       # Ensemble Logistic Regression code
├── ELR_predictions/          # ELR forecast outputs
├── cGAN_data/                # Model training data
├── run_forecast.py           # Main forecast generation script
├── start_forecasting.py      # Automatic forecasting script
├── main.py                   # FastAPI web server
├── Dockerfile                # Docker configuration
└── README.md                 # This file
```

---

## License

This project is maintained by ICPAC-IGAD for operational rainfall forecasting in East Africa.

---

**Last Updated:** December 2025

**Version:** 1.1.0

---

**Happy Forecasting! 🌧️📊**

If you encounter any problems not covered in this README, please don't hesitate to reach out or create an issue on GitHub. We're here to help!
