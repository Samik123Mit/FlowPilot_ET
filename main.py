"""FlowPilot -- Main application entry point."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Register routes
app.include_router(router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "service": "FlowPilot",
        "version": "1.0.0",
        "tagline": "From Meetings to Momentum",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
