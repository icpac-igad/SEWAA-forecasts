import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Literal
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel


class HealthCheckPayload(BaseModel):
    status: Literal["online", "offline", "maintenance"]
    code: Literal[200, 404, 403]


class GenForecastPayload(BaseModel):
    status: Literal["complete", "pending", "failed"]


app = FastAPI()

app.mount("/static", StaticFiles(directory="interface/static"), name="static")
app.mount("/data", StaticFiles(directory="interface/data"), name="data")

templates = Jinja2Templates(directory="interface")


@app.get("/")
async def visualize_forecasts(request: Request) -> HTMLResponse:
    """Application Landing Page"""
    return templates.TemplateResponse(request=request, name="index.html")


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
        request=request, name="ensemble_logistic_regression"
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
    accumulation: str | None = None, date: str | None = None, time: str | None = None
) -> GenForecastPayload:
    """
    Generate cGAN forecasts

    Parameters:

        - accumulation (optional): forecast accumulation period. One of 6h and 24h

        - date (optional): date for which the forecast is to be generated. Must be in the format YYYYMMDD. Defaults to date today.

        - time (optional): forecast initialization time. Valid for 6h accumulation forecast. Any of 0000, 0600, 1200 and 1800. Defaults to 0000.

    """
    params = ["python", "run_forecast.py"]
    if accumulation is not None:
        params.extend(["--accumulation", accumulation])
    if date is not None:
        params.extend(["--date", date])
    if time is not None:
        params.extend(["--time", time])
    subprocess.run(params)
    return GenForecastPayload(status="complete")


@app.get("/healthz")
async def health_check() -> HealthCheckPayload:
    """Application health check endpoint"""
    return HealthCheckPayload(status="online", code=200)
