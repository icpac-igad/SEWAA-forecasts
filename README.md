# SEWAA-forecasts

Scripts for operational rainfall forecasts in the ICPAC region.


## Installation

#### ECMWF data

To download the ECMWF data pre-processed for these scripts you will need access to the
ECMWF machine gbmc. Contact the Oxford or ICPAC team for further information.

#### Conda environment

A conda environment is required, to set this up run the following commands:

> `conda config --add channels conda-forge`
> `conda config --set channel_priority strict`
> `conda create -n tf215gpu python=3.11`
> `conda activate tf215gpu`
> `python -m pip install tensorflow==2.15`
> `pip install numba`
> `pip install matplotlib`
> `pip install seaborn`
> `pip install cartopy`
> `pip install jupyter`
> `pip install xarray`
> `pip install netcdf4`
> `pip install scikit-learn`
> `pip install cfgrib`
> `pip install dask`
> `pip install tqdm`
> `pip install properscoring`
> `pip install climlab`
> `pip install iris`
> `pip install ecmwf-api-client`
> `pip install xesmf`
> `pip install flake8`

Check that tensor flow is working

> `python -c "import tensorflow as tf; print(tf.config.list_physical_devices('CPU'))"`

#### Forecast scripts

Go to https://github.com/Fenwick-Cooper/SEWAA-forecasts
Click on the big green button labelled "<> Code "
Select "Download ZIP"
Uncompress the SEWAA-forecasts-main.zip.


## How to use

#### To make a forecast

Run the script `run_forecast.py` that is located in the SEWAA-forecasts-main directory.
To get usage information run

> `python run_forecast.py --help`

Running 

> `python run_forecast.py`

will
1. Download the ECMWF data for 6h accumulations from gbmc.
2. Run the forecasts.
3. Process the forecast data for viewing.

#### To view the forecasts

In a terminal change to this directory and run

> `python3 -m http.server 8080 -d interface`
   
Then in a browser window go to the address

> http://localhost:8080/


## Roadmap

### Update to new cGAN

1. Implement scripts for new cGAN models.
2. Finalise working new models on github.
3. Place working data (weights, elevation etc online).

### Combine with HTML interface

1. Add HTML interface.
2. Update HTML interface with list of improvements.
3. Add ELR quality plots to HTML interface.

### Add ELR

1. Implement ELR scripts for ELR models.
2. ELR interface python prototype.
3. Add ELR to HTML interface.

### Prepare for remote install

1. Make all paths relative to base directory.
2. Download from gbmc instead of ECMWF
3. Remove upload to gbmc
4. Make prototype cGAN installation script for Windows/Linux/Mac.

