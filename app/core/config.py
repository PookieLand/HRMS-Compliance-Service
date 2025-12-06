from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Compliance Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Settings
    DB_NAME: str = "compliance_db"
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

    # JWT/JWKS Settings
    JWKS_URL: str = "https://api.asgardeo.io/t/pookieland/oauth2/jwks"
    JWT_AUDIENCE: str | None = (
        None  # Set to None to skip audience validation, or set to your client_id
    )
    JWT_ISSUER: str | None = (
        None  # Set to None to skip issuer validation, or set to expected issuer
    )

    # External Service URLs
    EMPLOYEE_SERVICE_URL: str = "http://localhost:8001"
    USER_MANAGEMENT_SERVICE_URL: str = "http://localhost:8002"

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


# Create global settings instance
settings = Settings()
