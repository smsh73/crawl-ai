"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from src.core.config import settings
from src.core.database import init_db

from .routes import sources, keywords, contents, schedules, reports, health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("application_startup", app_name=settings.app_name)
    await init_db()
    yield
    # Shutdown
    logger.info("application_shutdown")


app = FastAPI(
    title="Crawl AI API",
    description="AI-Native Intelligence Platform for automated web crawling and analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(keywords.router, prefix="/api/v1/keywords", tags=["Keywords"])
app.include_router(contents.router, prefix="/api/v1/contents", tags=["Contents"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["Schedules"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }
