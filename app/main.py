from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.compliance import router as compliance_router
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global state for tracking service health
service_state = {
    "kafka_connected": False,
    "redis_connected": False,
    "database_ready": False,
}


def init_kafka():
    """Initialize Kafka producer and consumer."""
    try:
        from app.core.consumers import register_all_handlers
        from app.core.kafka import get_consumer, get_producer
        from app.core.topics import KafkaTopics

        # Initialize producer
        producer = get_producer()
        producer.connect()
        logger.info("Kafka producer initialized")

        # Initialize consumer with all topics
        consumer = get_consumer(topics=KafkaTopics.all_subscribed_topics())
        register_all_handlers(consumer)
        consumer.start()
        logger.info("Kafka consumer started with all handlers")

        service_state["kafka_connected"] = True
    except Exception as e:
        logger.error(f"Failed to initialize Kafka: {e}")
        service_state["kafka_connected"] = False


def shutdown_kafka():
    """Shutdown Kafka connections."""
    try:
        from app.core.kafka import get_consumer, get_producer

        # Stop consumer
        consumer = get_consumer()
        consumer.stop()
        logger.info("Kafka consumer stopped")

        # Disconnect producer
        producer = get_producer()
        producer.disconnect()
        logger.info("Kafka producer disconnected")

        service_state["kafka_connected"] = False
    except Exception as e:
        logger.error(f"Error shutting down Kafka: {e}")


def init_redis():
    """Initialize Redis cache."""
    try:
        from app.core.cache import init_cache

        cache = init_cache()
        service_state["redis_connected"] = cache.is_connected()
        if service_state["redis_connected"]:
            logger.info("Redis cache initialized successfully")
        else:
            logger.warning("Redis cache failed to connect")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis: {e}")
        service_state["redis_connected"] = False


def shutdown_redis():
    """Shutdown Redis connection."""
    try:
        from app.core.cache import close_cache

        close_cache()
        service_state["redis_connected"] = False
        logger.info("Redis cache closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup
    logger.info("Starting Compliance Service...")

    # Initialize database
    logger.info("Creating database and tables...")
    create_db_and_tables()
    service_state["database_ready"] = True
    logger.info("Database and tables created successfully")

    # Initialize Redis cache
    logger.info("Initializing Redis cache...")
    init_redis()

    # Initialize Kafka
    if settings.kafka_configured:
        logger.info("Initializing Kafka...")
        init_kafka()
    else:
        logger.warning("Kafka not configured, skipping initialization")

    logger.info("Compliance Service startup complete")

    yield

    # Shutdown
    logger.info("Compliance Service shutting down...")

    # Shutdown Kafka
    if service_state["kafka_connected"]:
        shutdown_kafka()

    # Shutdown Redis
    if service_state["redis_connected"]:
        shutdown_redis()

    logger.info("Compliance Service shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Compliance Service for HRMS - GDPR compliance, data inventory, and retention management",
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
app.include_router(compliance_router, prefix="/api/v1/compliance")


@app.get("/health", tags=["health"])
async def detailed_health_check():
    """
    Detailed health check endpoint with connection status.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "connections": {
            "database": service_state["database_ready"],
            "kafka": service_state["kafka_connected"],
            "redis": service_state["redis_connected"],
        },
    }


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """
    Readiness probe for Kubernetes.
    Returns 200 if service is ready to accept traffic.
    """
    is_ready = service_state["database_ready"]

    if is_ready:
        return {"status": "ready"}
    else:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/health/live", tags=["health"])
async def liveness_check():
    """
    Liveness probe for Kubernetes.
    Returns 200 if service is alive.
    """
    return {"status": "alive"}


@app.get("/health/kafka", tags=["health"])
async def kafka_health_check():
    """Kafka connection health check."""
    kafka_status = {}
    try:
        from app.core.kafka import health_check

        kafka_status = health_check()
    except Exception as e:
        kafka_status = {"error": str(e)}

    return {
        "enabled": settings.kafka_configured,
        "connected": service_state["kafka_connected"],
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "consumer_group": settings.KAFKA_CONSUMER_GROUP_ID,
        "details": kafka_status,
    }


@app.get("/health/redis", tags=["health"])
async def redis_health_check():
    """Redis connection health check."""
    connected = False
    try:
        from app.core.cache import get_cache_service

        cache = get_cache_service()
        connected = cache.is_connected()
    except Exception:
        pass

    return {
        "connected": connected,
        "host": settings.REDIS_HOST,
        "port": settings.REDIS_PORT,
    }


@app.get("/metrics/compliance", tags=["metrics"])
async def compliance_metrics():
    """
    Get compliance metrics for dashboard.
    """
    try:
        from datetime import date

        from app.core.cache import get_cache_service

        cache = get_cache_service()
        today = date.today().isoformat()

        # Try to get from cache first
        cached_metrics = cache.get_compliance_metrics(today)
        if cached_metrics:
            return cached_metrics

        # Calculate metrics if not cached
        from sqlmodel import Session, func, select

        from app.core.database import engine
        from app.models.data_inventory import DataCategory, DataInventory
        from app.models.employee_data_access import DataRetention

        with Session(engine) as session:
            # Count data inventory items
            inventory_count = session.exec(
                select(func.count()).select_from(DataInventory)
            ).one()

            # Count categories
            category_count = session.exec(
                select(func.count()).select_from(DataCategory)
            ).one()

            # Count retention records by status
            active_count = session.exec(
                select(func.count())
                .select_from(DataRetention)
                .where(DataRetention.retention_status == "active")
            ).one()

            expiring_count = session.exec(
                select(func.count())
                .select_from(DataRetention)
                .where(DataRetention.retention_status == "expiring_soon")
            ).one()

            expired_count = session.exec(
                select(func.count())
                .select_from(DataRetention)
                .where(DataRetention.retention_status == "expired")
            ).one()

        metrics = {
            "date": today,
            "data_inventory": {
                "total_items": inventory_count,
                "categories": category_count,
            },
            "retention": {
                "active_records": active_count,
                "expiring_soon": expiring_count,
                "expired_records": expired_count,
            },
            "counters": {
                "data_collected_today": cache.get_counter(f"data_collected:{today}"),
                "data_deleted_today": cache.get_counter(f"data_deleted:{today}"),
            },
        }

        # Cache the metrics
        cache.set_compliance_metrics(metrics, today)

        return metrics
    except Exception as e:
        logger.error(f"Error fetching compliance metrics: {e}")
        return {
            "error": "Unable to fetch metrics",
            "detail": str(e),
        }


@app.get("/", tags=["info"])
async def root():
    """Root endpoint with service information."""
    subscribed_topics = []
    try:
        from app.core.topics import KafkaTopics

        subscribed_topics = KafkaTopics.all_subscribed_topics()
    except Exception:
        pass

    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Compliance Service for HRMS - GDPR compliance and data management",
        "endpoints": {
            "health": "/health",
            "health_ready": "/health/ready",
            "health_live": "/health/live",
            "health_kafka": "/health/kafka",
            "health_redis": "/health/redis",
            "metrics": "/metrics/compliance",
            "data_inventory": "/api/v1/compliance/data-inventory",
            "data_about_me": "/api/v1/compliance/employee/{employee_id}/data-about-me",
            "retention_report": "/api/v1/compliance/data-retention-report",
            "docs": "/docs",
        },
        "kafka": {
            "enabled": settings.kafka_configured,
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "consumer_group": settings.KAFKA_CONSUMER_GROUP_ID,
            "topics_count": len(subscribed_topics),
            "topics_sample": subscribed_topics[:10] if subscribed_topics else [],
        },
        "redis": {
            "configured": settings.redis_configured,
            "host": settings.REDIS_HOST,
        },
        "gdpr_features": {
            "article_5_storage_limitation": True,
            "article_15_right_of_access": True,
            "article_17_right_to_erasure": settings.ENABLE_DATA_DELETION,
            "article_20_data_portability": settings.ENABLE_DATA_EXPORT,
            "article_30_records_of_processing": True,
        },
    }
