"""Download recent RFE2 daily truth for the ICPAC region."""
import ftplib, zipfile, os, io, time, sys
from datetime import date, timedelta
import numpy as np, netCDF4 as nc_lib, rasterio
from rasterio.mask import mask
import geopandas as gpd
from shapely.geometry import mapping
from shapely.ops import unary_union

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHP = os.path.join(SCRIPT_DIR, "shapes", "ICPAC_REGIONAL", "ICPAC_ADM0.shp")
ICPAC=[mapping(unary_union(gpd.read_file(SHP).geometry))]
FTP_HOST="ftp.cpc.ncep.noaa.gov"; FTP_DIR="/fews/fewsdata/africa/rfe2/geotiff/"
OUT_DIR = os.environ.get("RFE_OUT_DIR", os.path.join(SCRIPT_DIR, "RFE_truth"))

def tif_to_nc(tb,out_path,ds):
    with rasterio.MemoryFile(tb) as mf:
        with mf.open() as src:
            img,tr=mask(src,ICPAC,crop=True,nodata=-9999); d=img[0].astype("float32")
            h,w=d.shape
            lons=np.array([tr.c+(i+0.5)*tr.a for i in range(w)])
            lats=np.array([tr.f+(j+0.5)*tr.e for j in range(h)])
    os.makedirs(os.path.dirname(out_path),exist_ok=True)
    n=nc_lib.Dataset(out_path,"w",format="NETCDF4")
    n.createDimension("lat",h); n.createDimension("lon",w)
    la=n.createVariable("lat","f4",("lat",)); lo=n.createVariable("lon","f4",("lon",))
    p=n.createVariable("precipitation","f4",("lat","lon"),fill_value=-9999.0,zlib=True,complevel=4)
    la.units="degrees_north"; lo.units="degrees_east"; p.units="mm/day"
    la[:]=lats; lo[:]=lons; p[:]=np.where(d==-9999,-9999.0,d)
    n.source="RFEv2"; n.date=ds; n.region="ICPAC"; n.close()

dates=[d for d in sys.argv[1:]]
ftp=ftplib.FTP(FTP_HOST,timeout=90); ftp.login(); ftp.cwd(FTP_DIR)
avail=set(ftp.nlst()); ftp.quit()
for ds in dates:
    out=os.path.join(OUT_DIR,ds[:4],f"{ds}.nc")
    if os.path.exists(out): print(f"[SKIP] {ds} (already have it)"); continue
    fn=f"africa_rfe.{ds}.tif.zip"
    if fn not in avail: print(f"[MISS] {ds} — not yet published by NOAA (RFE2 lag)"); continue
    for a in range(3):
        try:
            ftp=ftplib.FTP(FTP_HOST,timeout=90); ftp.login(); ftp.cwd(FTP_DIR)
            buf=io.BytesIO(); ftp.retrbinary(f"RETR {fn}",buf.write); ftp.quit(); buf.seek(0)
            with zipfile.ZipFile(buf) as zf:
                tb=zf.read([x for x in zf.namelist() if x.endswith(".tif")][0])
            tif_to_nc(tb,out,ds); print(f"[OK]   {ds} -> {out}"); break
        except Exception as e:
            if a<2: time.sleep(8)
            else: print(f"[ERR]  {ds}: {e}")
