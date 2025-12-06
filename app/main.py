from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.compliance import router as compliance_router
from app.api.routes.inventory import router as inventory_router
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup
    logger.info("Starting Compliance Service...")
    logger.info("Creating database and tables...")
    create_db_and_tables()
    logger.info("Database and tables created successfully")
    logger.info("Compliance Service startup complete")

    yield

    # Shutdown
    logger.info("Compliance Service shutting down...")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Include routers
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def detailed_health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


"""
"service": "Compliance Service",
"endpoints": {
    "data_inventory": {
        "GET /api/v1/compliance/data-inventory": "Complete map of all data (GDPR Article 30)",
        "GET /api/v1/compliance/employee/{employee_id}/data-about-me": "Employee's personal data summary (GDPR Article 15)",
        "GET /api/v1/compliance/employee/{employee_id}/access-controls": "What data employee can access and why",
        "GET /api/v1/compliance/data-retention-report": "Data age and deletion requirements (GDPR Article 5)",
    },
    "inventory_management": {
        "POST /api/v1/compliance/inventory/categories": "Create data category",
        "GET /api/v1/compliance/inventory/categories": "List all categories",
        "POST /api/v1/compliance/inventory/entries": "Create inventory entry",
        "GET /api/v1/compliance/inventory/entries": "List inventory entries",
    },
    "authentication": {
        "GET /api/v1/auth/whoami": "Get current user info",
        "GET /api/v1/auth/verify": "Verify JWT token",
        "GET /api/v1/auth/debug": "Debug token contents",
    },
"""
