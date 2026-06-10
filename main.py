import subprocess
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import Literal
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path


class HealthCheckPayload(BaseModel):
    status: Literal["online", "offline", "maintenance"]
    code: Literal[200, 404, 403]


class GenForecastPayload(BaseModel):
    status: Literal["started", "complete", "pending", "failed"]


app = FastAPI(
    title="SEWAA Forecasts API",
    description="Backend API for SEWAA cGAN forecast generation",
)

api = FastAPI(
    title="SEWAA Forecasts API",
    description="Backend API for SEWAA cGAN forecast generation",
)

# Jinja2 templates
templates = Jinja2Templates(directory="interface")

# Mount data and static directories
data_dir = Path("interface/data")
if not data_dir.exists():
    data_dir.mkdir(parents=True)
app.mount("/static", StaticFiles(directory="interface/static"), name="static")
app.mount("/data", StaticFiles(directory=data_dir), name="data")


# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/{page}.html", response_class=HTMLResponse)
async def page(request: Request, page: str):
    return templates.TemplateResponse(f"{page}.html", {"request": request})


# Mount the API sub-application
app.mount("/api", api)


@api.get("/app-status")
async def health_check() -> HealthCheckPayload:
    """Application health check endpoint"""
    return HealthCheckPayload(status="online", code=200)


@api.get("/gen-forecast")
async def generate_forecasts(
    accumulation: Literal["6h", "24h"] | None = None,
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    forecast_date: str | None = datetime.today().strftime("%Y%m%d"),
    delete_forecasts: Literal["Y", "N"] | None = "Y",
) -> GenForecastPayload:
    """
    Generate cGAN forecasts

    Parameters:

        - accumulation (optional): forecast accumulation period. One of 6h and 24h

        - date (optional): date for which the forecast is to be generated. Must be in the format YYYYMMDD. Defaults to date today.

        - time (optional): forecast initialization time. Valid for 6h accumulation forecast. Any of 0000, 0600, 1200 and 1800. Defaults to 0000.

    """
    params = ["python", "run_forecast.py", "--delete_forecasts", delete_forecasts]
    if accumulation is not None:
        params.extend(["--accumulation", accumulation])
    if forecast_date is not None:
        params.extend(["--date", forecast_date])
    if time is not None:
        params.extend(["--time", time])
    subprocess.run(params)
    return GenForecastPayload(status="started")
