import os
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Literal
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import markdown2

COMBINED_MODE = os.environ.get("COMBINED_MODE", "false").lower() == "true"


class HealthCheckPayload(BaseModel):
    status: Literal["online", "offline", "maintenance"]
    code: Literal[200, 404, 403]


class GenForecastPayload(BaseModel):
    status: Literal["started", "complete", "pending", "failed"]


app = FastAPI()

# ensure static data paths exist before mounting to path
static_dir = Path("interface/static")
if not static_dir.exists():
    static_dir.mkdir(parents=True)

# Viz-ready data lives in the data store, ${STORE:-./store}/interface/<dataset> (see
# docker-compose.yml), which is shared with other consumers (e.g. cgan-cms) and so must not
# be restructured to suit this app. Under docker-compose the IMERG tree is mounted at
# interface/data instead and no store exists in the container, so fall back to that.
store_interface_dir = Path(os.path.expandvars(os.environ.get("STORE", "store"))) / "interface"

data_dir = store_interface_dir / "imerg"
if not data_dir.is_dir():
    data_dir = Path("interface/data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True)


elr_climate_dir = Path("ELR/climatological_exceedances")


app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Mirror the nginx data portal (configs/nginx.conf): IMERG at /data/, the others under it.
# Registered before /data so they take precedence.
for dataset in ("rfe", "chirps"):
    if (store_interface_dir / dataset).is_dir():
        app.mount(f"/data/{dataset}", StaticFiles(directory=store_interface_dir / dataset), name=f"data_{dataset}")
app.mount("/data", StaticFiles(directory=data_dir), name="data")
app.mount("/staticELR_climate", StaticFiles(directory=elr_climate_dir), name="elr_climate")

templates = Jinja2Templates(directory="interface")


@app.get("/")
async def visualize_forecasts(request: Request) -> HTMLResponse:
    """Application Landing Page"""
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"combined_mode": COMBINED_MODE},
    )


@app.get("/app-status")
async def health_check() -> HealthCheckPayload:
    """Application health check endpoint"""
    return HealthCheckPayload(status="online", code=200)


@app.get("/index.html")
async def get_index_page() -> RedirectResponse:
    return RedirectResponse(url="/")


@app.get("/showForecasts.html")
async def get_show_forecasts(request: Request) -> HTMLResponse:
    """Render Forecasts Visualization Page"""
    return templates.TemplateResponse(
        request=request, name="showForecasts.html",
        context={"combined_mode": COMBINED_MODE},
    )


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


@app.get("/CRPS_comparison.html")
async def get_crps_comparison(request: Request) -> HTMLResponse:
    """Render CRPS Comparison Page"""
    return templates.TemplateResponse(request=request, name="CRPS_comparison.html")


@app.get("/user-guide")
async def get_user_guide(request: Request) -> HTMLResponse:
    """Render the User Guide page"""
    return templates.TemplateResponse(request=request, name="user_guide.html")


@app.get("/documentation")
async def get_documentation(request: Request) -> HTMLResponse:
    """Render README.md as styled HTML documentation"""
    readme_path = Path("README.md")
    md_content = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "# Documentation\n\nNo README.md found."
    html_content = markdown2.markdown(md_content, extras=["fenced-code-blocks", "tables", "header-ids"])
    return templates.TemplateResponse(
        request=request,
        name="documentation.html",
        context={"doc_content": html_content},
    )


@app.get("/gen-forecast")
async def generate_forecasts(
    accumulation: Literal["6h", "24h"] | None = None,
    time: Literal["0000", "0600", "1200", "1800"] | None = "0000",
    forecast_date: str | None = None,
    delete_forecasts: Literal["Y", "N"] | None = "Y",
) -> GenForecastPayload:
    """
    Generate cGAN forecasts

    Parameters:

        - accumulation (optional): forecast accumulation period. One of 6h and 24h

        - date (optional): date for which the forecast is to be generated. Must be in the format YYYYMMDD. Defaults to date today.

        - time (optional): forecast initialization time. Valid for 6h accumulation forecast. Any of 0000, 0600, 1200 and 1800. Defaults to 0000.

    """
    # Resolved per request: a default in the signature would be frozen at server start.
    if forecast_date is None:
        forecast_date = datetime.today().strftime("%Y%m%d")
    params = ["python", "run_forecast.py", "--delete_forecasts", delete_forecasts, "--date", forecast_date]
    if accumulation is not None:
        params.extend(["--accumulation", accumulation])
    if time is not None:
        params.extend(["--time", time])
    # Run in the background: a forecast takes minutes, and waiting on it here would tie up
    # one of the (few) API workers for the whole run.
    subprocess.Popen(params)
    return GenForecastPayload(status="started")
