"""
Shared API dependencies.
Contains reusable dependency functions for FastAPI endpoints.
Centralizes common dependencies like database sessions, authentication (future), etc.
"""

from typing import Annotated
from fastapi import Depends
from sqlmodel import Session

from app.core.database import get_session


# Database session dependency
# Use this type annotation in route handlers to get automatic session injection
SessionDep = Annotated[Session, Depends(get_session)]


# Future dependencies can be added here:
# - CurrentUserDep: Get current authenticated user
# - RequireAdminDep: Verify admin permissions
# - RateLimitDep: Rate limiting
# etc.
