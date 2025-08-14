import os
import glob
import argparse
from datetime import datetime
import warnings

import numpy as np
from tqdm import tqdm
import xarray as xr
import joblib

from file_paths import paths
from helper_functions import get_geometry
import regionmask
from sklearn.exceptions import InconsistentVersionWarning


OUT_PATH = paths['OUT_PATH']
FCST_PATH = paths['FCST_PATH']
MODEL_PATH = paths['MODEL_PATH']

if not os.path.exists(OUT_PATH):
    os.makedirs(OUT_PATH)

countries = ['Ethiopia','Kenya']
county = True
subcounty = True

counties = None
subcounties = None

def get_model_output(date, accumulation = "6h_accumulations", model="GAN", day=1):

    if model == 'GAN':
        fcst_root_dir = f'{FCST_PATH}/{accumulation}/cGAN_forecasts/'
    elif model=='IFS':
        fcst_root_dir = f'{FCST_PATH}/{accumulation}/{model}_forecast_data/'

    if accumulation == "6h_accumulations":
        ds_fcst = xr.open_dataset(fcst_root_dir+f'{model}_{date}_00Z.nc')
        ds_fcst = ds_fcst.mean("valid_time")
        ds_fcst['fcst_valid_time'] = xr.DataArray(ds_fcst.time.values+np.timedelta64(30,'h'),dims=['time'],
                                                  coords={'time':ds_fcst.time.values})
    else:
        ds_fcst = xr.open_dataset(fcst_root_dir+f'{model}_{date}_00Z_v{day}.nc')
        ds_fcst = ds_fcst.isel({"valid_time":0})

    return ds_fcst
    
def get_region(Location, geometry_all, ds):
    region_vectorised = regionmask.Regions(geometry_all, names=[Location])
    
    ## follows syntax of lat/lon
    mask_list = region_vectorised.mask_3D(ds.rename({'longitude':'lon','latitude':'lat'}))
    mask_list = np.ma.masked_invalid(mask_list)  

    temp = ds.precipitation.where(mask_list[0]).stack(latlon=('longitude','latitude'))
    fcst_valid_time = ds.fcst_valid_time
    ds_sel = temp.drop_vars(\
                ['latlon', 'longitude', 'latitude']
            ).assign_coords({'latlon':np.arange(temp[0].latlon.values.shape[0]),
                            'latitude':('latlon',[val[1] for val in temp[0].latlon.values]),
                            'longitude':('latlon',[val[0] for val in\
                                                   temp[0].latlon.values])}).dropna('latlon').reset_index('latlon')
    if Location=='Kajiado-East':
        ds_sel = ds_sel.isel({'latlon':slice(0,10)})
    ds_sel['fcst_valid_time']=fcst_valid_time

    return ds_sel

def get_model_checkpoint(Location, country, day, model):

    if country == 'Kenya':

        return '1'
        
    elif country=='Ethiopia':
        return str(day)
    

def get_ELR_predictions(logreg_model, model, ds_sel, day, Location, date, save_path, return_ds=False):
    timedelta = np.timedelta64(day,'D')+np.timedelta64(6,'h')
    if not return_ds:
        file_name = save_path+f'{model}_{Location}_{date}_logreg.zarr'
        timedelta = np.timedelta64(day,'D')+np.timedelta64(6,'h')
        
        if os.path.exists(file_name):
            precheck = xr.open_zarr(file_name)
            if ds_sel.time.values+timedelta in precheck.fcst_valid_time.values:
                print('predictions already made, skipping')
                return
    else:
        file_name = save_path+f'{model}_{Location}_{date}_logreg.nc'
        if os.path.exists(file_name):
            print('file already exists under,',file_name,'delete first then retry')
            return

    thresholds = np.asarray([key for key in logreg_model.keys()])
    latitude_reg = ds_sel.latitude.values
    longitude_reg = ds_sel.longitude.values
    date = ds_sel.time.values[0].astype('datetime64[D]').astype(object).strftime("%Y%M%d")

    lons, lats = np.meshgrid(np.unique(longitude_reg),np.unique(latitude_reg))
    predictions = np.full([1,1,thresholds.shape[0],lats.shape[0],lats.shape[1]],np.nan)
    
    mask = np.full([lats.shape[0],lats.shape[1]],False)
    
    for lat_reg,lon_reg in zip(latitude_reg,longitude_reg):
    
        idx_2d = np.ma.asarray(lats==lat_reg) * np.ma.asarray(lons==lon_reg)
        mask[idx_2d] = True
    
    X = np.sort(np.squeeze(24*ds_sel.values),axis=0).T

    if model == 'GAN':

        X = np.percentile(X, np.linspace(1,100,50), axis=1, method='weibull').T
    
    for i, threshold in enumerate(thresholds):
        predictions[0,0,i,mask] = logreg_model[threshold].predict_proba(X)[:,1]

    ds_predictions = xr.DataArray(predictions, dims = ['time','fcst_valid_time','threshold','latitude','longitude'],
                                  coords = {\
                                      'time': ds_sel.time.values,
                                      'fcst_valid_time': ds_sel.time.values+timedelta,
                                      'threshold': thresholds,
                                      'latitude': np.unique(latitude_reg),
                                      'longitude': np.unique(longitude_reg),
                                  }
                                 ).rename('probability_exceedance')

    if return_ds:
        return ds_predictions

    else:
        if os.path.exists(file_name):
            ds_predictions.to_zarr(file_name, mode='a-',append_dim='fcst_valid_time')
        else:
            ds_predictions.to_zarr(file_name, mode='w')

    

if __name__=='__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='IFS or GAN',default=None)
    parser.add_argument('--model', help='IFS or GAN',default='GAN',type=str)
    parser.add_argument('--day', help='lead time (in days)',action='append',nargs='+',default=None,type=int)
    parser.add_argument('--accumulation', help='6h- or 24h- accumulation',default="24h_accumulations",type=str)
    parser.add_argument('--store_netcdf', help='Store as netcdf (otherwise zarr is used)',default=True,action='store_true')
    
    args = parser.parse_args()

    
    date = args.date
    if date is None:
        date = np.array(['2024-04-23'],dtype='datetime64[D]')[0].astype(object).strftime("%Y%m%d")#datetime.now().strftime("%Y%M%d")
    model = args.model
    day = args.day
    if day is None:
        day = np.arange(2,6)
    else:
        day = day[0]
    store_netcdf = args.store_netcdf
    accumulation = args.accumulation
    #with tqdm(total=len(countries)*len(day)) as pbar:
    for country in countries:

        if store_netcdf:
            ds_subcounty = {}
            ds_county = {}

        county_loop = county
        subcounty_loop = subcounty

        if not os.path.exists(OUT_PATH+f'{country}/'):
            os.makedirs(OUT_PATH+f'{country}/')

        if counties == None and county:
            counties_loop = glob.glob(MODEL_PATH+f'{country}/counties/*')
            counties_loop = [c.split('counties')[-1].split('_')[0].replace('/','').replace('\\','') for c in counties_loop]
        
        if len(counties_loop)==0 and county:
            print("No county-level models found for:",country)
            county_loop=False
    
        if subcounties == None and subcounty:
            subcounties_loop = glob.glob(MODEL_PATH+f'{country}/subcounties/*')
            subcounties_loop = [c.split('subcounties')[-1].split('_')[0].replace('/','').replace('\\','') for c in subcounties_loop]
    
        if len(subcounties_loop)==0 and subcounty:
            print("No subcounty-level models found for:",country)
            subcounty_loop=False

        for Location in counties_loop:
            skip_county = True
            if not os.path.exists(OUT_PATH+f'{accumulation}/{country}/county/{model}_{Location}_{date}_logreg.nc'):
                skip_county=False

        for Location in subcounties_loop:
            skip_subcounty = True
            if not os.path.exists(OUT_PATH+f'{accumulation}/{country}/subcounty/{model}_{Location}_{date}_logreg.nc'):
                skip_subcounty=False

        if skip_county and skip_subcounty:
            print(f"All ELR predictions already made for {country} at {accumulation}, skipping")
            continue
        print(f'Calculating ELR output for {accumulation} in {country}')
        for d in day:
            d = int(d)
            assert isinstance(d,int)
            ds = get_model_output(date, accumulation = accumulation, model=model, day=d)
    
            if subcounty_loop:
                
                if not os.path.exists(OUT_PATH+f'{country}/subcounty/'):
                    os.makedirs(OUT_PATH+f'{country}/subcounty/')
                
                for Location in subcounties_loop:
                    if store_netcdf:
                        if Location not in [key for key in ds_subcounty.keys()]:
                            ds_subcounty[Location] = []
        
                    #print("Getting ELR predictions for", Location)
    
                    geometry_all = get_geometry(Location, region_type='subcounty', country=country)
                    ds_sel = get_region(Location, geometry_all, ds)
                    checkpoint = get_model_checkpoint(Location, country, d, model)
                    if model=='GAN':
                        warnings.filterwarnings('ignore', category=InconsistentVersionWarning)
                        logreg_model = joblib.load(MODEL_PATH+f'{country}/subcounties/{Location}_logreg_models.pkl')[checkpoint]['cGAN']
                    else:
                        logreg_model = joblib.load(MODEL_PATH+f'{country}/subcounties/{Location}_logreg_models.pkl')[checkpoint][model]
    
                    if store_netcdf:
                        ds_subcounty[Location].append(get_ELR_predictions(logreg_model, model, ds_sel, d, 
                                                                Location, date, OUT_PATH+f'{country}/subcounty/',return_ds=store_netcdf))
                    else:
                        get_ELR_predictions(logreg_model, model, ds_sel, d, 
                                                                Location, date, OUT_PATH+f'{country}/subcounty/',return_ds=store_netcdf)
        
            if county_loop:
                if not os.path.exists(OUT_PATH+f'{country}/county/'):
                    os.makedirs(OUT_PATH+f'{country}/county/')
                
                for Location in counties_loop:
                    if store_netcdf:
                        if Location not in [key for key in ds_county.keys()]:
                            ds_county[Location] = []
                    #print("Getting ELR predictions for", Location)
    
                    geometry_all = get_geometry(Location, region_type='county', country=country)
                    ds_sel = get_region(Location, geometry_all, ds)
                    checkpoint = get_model_checkpoint(Location, country, d, model)
                    if model=='GAN':
                        logreg_model = joblib.load(MODEL_PATH+f'{country}/counties/{Location}_logreg_models.pkl')[checkpoint]['cGAN']
                    else:
                        logreg_model = joblib.load(MODEL_PATH+f'{country}/counties/{Location}_logreg_models.pkl')[checkpoint][model]
    
                    if store_netcdf:
                        ds_county[Location].append(get_ELR_predictions(logreg_model, model, ds_sel, d, 
                                                                        Location, date, OUT_PATH+f'{accumulation}/{country}/county/',
                                                                       return_ds=store_netcdf))
                    else:
                         get_ELR_predictions(logreg_model, model, ds_sel, d, 
                                                                Location, date, OUT_PATH+f'{accumulation}/{country}/county/',
                                                                return_ds=store_netcdf)
        #pbar.update(1)
        if store_netcdf:
            if subcounty_loop:
                for Location in ds_subcounty.keys():
                    if not os.path.exists(OUT_PATH+f'{accumulation}/{country}/subcounty/'):
                        os.makedirs(OUT_PATH+f'{accumulation}/{country}/subcounty/')
                    file_name = OUT_PATH+f'{accumulation}/{country}/subcounty/{model}_{Location}_{date}_logreg.nc'
                    if os.path.exists(file_name):
                        continue
                    else:
                        xr.concat(ds_subcounty[Location],'fcst_valid_time').to_netcdf(file_name)
    
            if county_loop:
                for Location in ds_county.keys():
                    if not os.path.exists(OUT_PATH+f'{accumulation}/{country}/county/'):
                        os.makedirs(OUT_PATH+f'{accumulation}/{country}/county/')
                    file_name = OUT_PATH+f'{accumulation}/{country}/county/{model}_{Location}_{date}_logreg.nc'
                    if os.path.exists(file_name):
                        continue
                    else:
                        xr.concat(ds_county[Location],'fcst_valid_time').to_netcdf(file_name)
        
                        
                    
