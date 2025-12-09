from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Compliance Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Settings
    DB_NAME: str = "hrms_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_CHARSET: str = "utf8"

    # CORS Settings
    CORS_ORIGINS: str = "https://localhost,http://localhost:3000"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string."""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return [self.CORS_ORIGINS]

    # ==========================================
    # Kafka Configuration
    # ==========================================
    KAFKA_ENABLED: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP_ID: str = "compliance-service-group"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_ENABLE_AUTO_COMMIT: bool = False
    KAFKA_MAX_POLL_INTERVAL_MS: int = 300000
    KAFKA_SESSION_TIMEOUT_MS: int = 45000
    KAFKA_HEARTBEAT_INTERVAL_MS: int = 15000

    @property
    def kafka_configured(self) -> bool:
        """Check if Kafka is properly configured."""
        return bool(self.KAFKA_ENABLED and self.KAFKA_BOOTSTRAP_SERVERS)

    # ==========================================
    # Redis Configuration
    # ==========================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # Cache TTL Settings (in seconds)
    CACHE_TTL_INVENTORY: int = 300  # 5 minutes for data inventory
    CACHE_TTL_EMPLOYEE_DATA: int = 300  # 5 minutes for employee data summary
    CACHE_TTL_RETENTION: int = 300  # 5 minutes for retention reports
    CACHE_TTL_METRICS: int = 300  # 5 minutes for metrics
    CACHE_TTL_DEDUP: int = 86400  # 24 hours for event deduplication
    CACHE_TTL_ACCESS_CONTROLS: int = 600  # 10 minutes for access controls
    CACHE_TTL_CATEGORIES: int = 3600  # 1 hour for data categories

    @property
    def redis_configured(self) -> bool:
        """Check if Redis is properly configured."""
        return bool(self.REDIS_HOST and self.REDIS_PORT)

    # ==========================================
    # Asgardeo/JWT Settings
    # ==========================================
    ASGARDEO_ORG: str = "pookieland"
    ASGARDEO_CLIENT_ID: str = ""
    JWT_AUDIENCE: str | None = None
    JWT_ISSUER: str | None = None

    @property
    def jwks_url(self) -> str:
        """Generate JWKS URL from Asgardeo organization."""
        return f"https://api.asgardeo.io/t/{self.ASGARDEO_ORG}/oauth2/jwks"

    @property
    def token_url(self) -> str:
        """Generate token endpoint URL from Asgardeo organization."""
        return f"https://api.asgardeo.io/t/{self.ASGARDEO_ORG}/oauth2/token"

    # ==========================================
    # External Service URLs
    # ==========================================
    EMPLOYEE_SERVICE_URL: str = "http://localhost:8001"
    USER_SERVICE_URL: str = "http://localhost:8000"

    # ==========================================
    # Compliance Service Specific Settings
    # ==========================================
    # Data Retention Settings (per GDPR Article 5 - Storage Limitation)
    DEFAULT_RETENTION_DAYS: int = 365  # Default retention period
    RETENTION_WARNING_DAYS: int = 30  # Days before expiration to send warning
    RETENTION_CHECK_INTERVAL_HOURS: int = 24  # How often to check retention

    # GDPR Compliance Settings
    ENABLE_DATA_EXPORT: bool = True  # Article 20 - Data Portability
    ENABLE_DATA_DELETION: bool = True  # Article 17 - Right to Erasure
    ENABLE_DATA_ACCESS_LOGS: bool = True  # Track who accesses what data
    MAX_EXPORT_SIZE_MB: int = 100  # Maximum size for data export

    @property
    def database_url(self) -> str:
        """Generate MySQL database URL."""
        return f"mysql+mysqldb://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset={self.DB_CHARSET}"

    @property
    def database_url_without_db(self) -> str:
        """Generate MySQL URL without database name (for initial connection)."""
        return f"mysql+mysqldb://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}?charset={self.DB_CHARSET}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra env vars like JWKS_URL without validation errors


# Create global settings instance
settings = Settings()
