"""
Employee Data Access and Data Retention models.
Tracks what data employees can access and implements GDPR Article 5 (Storage Limitation).
"""

from sqlmodel import Field, SQLModel
from datetime import datetime


class EmployeeDataAccess(SQLModel, table=True):
    """
    Employee Data Access Control table model.
    Tracks which employee can access which data and why.
    Implements role-based and attribute-based access control.
    """

    id: int | None = Field(default=None, primary_key=True)
    employee_id: str = Field(index=True, max_length=255, nullable=False)
    data_inventory_id: int = Field(foreign_key="datainventory.id", nullable=False)
    access_level: str = Field(
        max_length=50, nullable=False
    )  # read, write, delete, admin
    access_reason: str = Field(
        max_length=500, nullable=False
    )  # Why they need access (e.g., "Manager of department X")
    role_based: bool = Field(
        default=True
    )  # True if access is through role, False if direct grant
    role_name: str | None = Field(default=None, max_length=100)
    granted_by: str | None = Field(default=None, max_length=255)
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DataRetention(SQLModel, table=True):
    """
    Data Retention tracking table model.
    Tracks data age and identifies what needs to be deleted.
    Implements GDPR Article 5 - Storage Limitation.
    """

    id: int | None = Field(default=None, primary_key=True)
    data_inventory_id: int = Field(foreign_key="datainventory.id", nullable=False)
    record_id: str = Field(
        max_length=255, nullable=False
    )  # ID of actual data record (e.g., user_id)
    data_created_at: datetime = Field(
        nullable=False
    )  # When the actual data was created
    data_last_accessed: datetime | None = Field(
        default=None
    )  # Last time this data was accessed
    retention_expires_at: datetime = Field(nullable=False)  # When retention period ends
    retention_status: str = Field(
        default="active", max_length=50, nullable=False
    )  # active, expiring_soon, expired, deleted
    marked_for_deletion: bool = Field(default=False)
    marked_for_deletion_at: datetime | None = Field(default=None)
    deletion_completed_at: datetime | None = Field(default=None)
    deletion_reason: str | None = Field(default=None, max_length=500)
    data_subject_id: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
