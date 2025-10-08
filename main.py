import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from typing import Literal

from fastapi.templating import Jinja2Templates

from pydantic import BaseModel


class HealthCheckPayload(BaseModel):
    status: Literal["online", "offline", "maintenance"]
    code: Literal[200, 404, 403]


class GenForecastPayload(BaseModel):
    status: Literal["complete", "pending", "failed"]


app = FastAPI()


templates = Jinja2Templates(directory="interface")


@app.get("/")
async def visualize_forecasts(request: Request) -> HTMLResponse:
    """Application Landing Page"""
    return templates.TemplateResponse(
        request=request, name="index.html", context={"id": 10}
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
