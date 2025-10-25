import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Literal
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from auto_gen import auto_gen_forecasts


class HealthCheckPayload(BaseModel):
    status: Literal["online", "offline", "maintenance"]
    code: Literal[200, 404, 403]


class GenForecastPayload(BaseModel):
    status: Literal["complete", "pending", "failed"]


app = FastAPI()

# ensure static data paths exist before mounting to path
static_dir = Path("interface/static")
if not static_dir.exists():
    static_dir.mkdir(parents=True)

data_dir = Path("interface/data")
if not data_dir.exists():
    data_dir.mkdir(parents=True)


app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/data", StaticFiles(directory=data_dir), name="data")

templates = Jinja2Templates(directory="interface")


@app.get("/")
async def visualize_forecasts(request: Request) -> HTMLResponse:
    """Application Landing Page"""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/healthz")
async def health_check() -> HealthCheckPayload:
    """Application health check endpoint"""
    return HealthCheckPayload(status="online", code=200)


@app.get("/index.html")
async def get_index_page() -> RedirectResponse:
    return RedirectResponse(url="/")


@app.get("/showForecasts.html")
async def get_show_forecasts(request: Request) -> HTMLResponse:
    """Render Forecasts Visualization Page"""
    return templates.TemplateResponse(request=request, name="showForecasts.html")


@app.get("/ensemble_logistic_regression.html")
async def get_ensemble_logistic_regression(request: Request) -> HTMLResponse:
    """Render Ensemble Logistic Regression Page"""
    return templates.TemplateResponse(
        request=request, name="ensemble_logistic_regression.html"
    )


@app.get("/costLossRatios.html")
async def get_cost_loss_ratios(request: Request) -> HTMLResponse:
    """Render Cost Loss Ratios Page"""
    return templates.TemplateResponse(request=request, name="costLossRatios.html")


@app.get("/categoriesOfReliability.html")
async def get_categories_of_reliability(request: Request) -> HTMLResponse:
    """Render Categories Of Reliability Page"""
    return templates.TemplateResponse(
        request=request, name="categoriesOfReliability.html"
    )


@app.get("/gen-forecast")
async def generate_forecasts(
    accumulation: Literal["6h", "24h"] | None = None,
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    forecast_date: str | None = None,
) -> GenForecastPayload:
    """
    Generate cGAN forecasts

    Parameters:

        - accumulation (optional): forecast accumulation period. One of 6h and 24h

        - date (optional): date for which the forecast is to be generated. Must be in the format YYYYMMDD. Defaults to date today.

        - time (optional): forecast initialization time. Valid for 6h accumulation forecast. Any of 0000, 0600, 1200 and 1800. Defaults to 0000.

    """
    params = ["python", "run_forecast.py", "--delete_forecasts", "Y"]
    if accumulation is not None:
        params.extend(["--accumulation", accumulation])
    if forecast_date is not None:
        params.extend(["--date", forecast_date])
    if time is not None:
        params.extend(["--time", time])
    subprocess.run(params)
    return GenForecastPayload(status="forecast generation started")


@app.get("/auto-gen-forecasts")
async def auto_generate_forecasts(
    start_date: str | None = None,
    final_date: str | None = None,
    accumulation: Literal["6h", "24h"] | None = "6h",
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    api_url: str | None = "http://localhost:8000/gen-forecast",
) -> list[str]:
    auto_gen_forecasts(
        start_date=start_date,
        final_date=final_date,
        accumulation=accumulation,
        time=time,
        api_url=api_url,
    )
