"""FlowPilot -- Main application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.api.websocket import ws_router
from src.models.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(
    title="FlowPilot",
    description="AI-Powered Autonomous Meeting-to-Action Intelligence System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)
app.include_router(ws_router)

# Serve sample meeting data files
DATA_DIR = Path(__file__).parent / "data"
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# Dashboard HTML path
DASHBOARD_HTML = Path(__file__).parent / "src" / "dashboard" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to dashboard."""
    return '<html><head><meta http-equiv="refresh" content="0;url=/dashboard"></head></html>'


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the FlowPilot dashboard."""
    if DASHBOARD_HTML.exists():
        return HTMLResponse(content=DASHBOARD_HTML.read_text(), status_code=200)
    return HTMLResponse(
        content="<h1>Dashboard not found</h1><p>Expected at src/dashboard/index.html</p>",
        status_code=404,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
