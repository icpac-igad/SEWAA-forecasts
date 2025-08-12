# SEWAA-forecasts

Scripts for operational rainfall forecasts in the ICPAC region.


## Installation

#### ECMWF data

To download the ECMWF data pre-processed for these scripts you will need access to the
ECMWF machine gbmc. Contact the Oxford or ICPAC team for further information.

#### Conda environment

A conda environment is required, to set this up run the following commands:

	conda config --add channels conda-forge
	conda config --set channel_priority strict
	conda create -n tf215gpu python=3.11
	conda activate tf215gpu
	python -m pip install tensorflow==2.15
	pip install numba
	python pip install matplotlib
	python pip install seaborn
	python pip install cartopy
	python pip install jupyter
	python pip install xarray
	python pip install netcdf4
	python pip install scikit-learn
	python pip install cfgrib
	python pip install dask
	python pip install tqdm
	python pip install properscoring
	python pip install climlab
	python pip install iris
	python pip install ecmwf-api-client
	python pip install xesmf
	python pip install flake8
	python pip install regionmask

Check that tensor flow is working

	python -c "import tensorflow as tf; print(tf.config.list_physical_devices('CPU'))"

#### Forecast scripts

- Go to https://github.com/Fenwick-Cooper/SEWAA-forecasts.
- Click on the big green button labelled "<> Code ".
- Select "Download ZIP".
- Uncompress the SEWAA-forecasts-main.zip.


## How to use

#### To make a forecast

Run the script `run_forecast.py` that is located in the SEWAA-forecasts-main directory.
To get usage information run

	python run_forecast.py --help

Running 

	conda activate tf215gpu
	python run_forecast.py

will
1. Download the ECMWF data for 6h accumulations from gbmc.
2. Run the forecasts.
3. Process the forecast data for viewing.

#### To view the forecasts

In a terminal change to the SEWAA-forecasts-main directory and run

	python -m http.server 8080 -d interface
   
Then in a browser window go to the address

> http://localhost:8080/
