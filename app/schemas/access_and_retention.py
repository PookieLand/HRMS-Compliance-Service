"""
Employee Data Access and Data Retention Pydantic schemas.
Defines request/response models for access control and retention tracking endpoints.
"""

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class EmployeeDataAccessBase(SQLModel):
    """Base schema for employee data access with shared fields."""

    employee_id: str = Field(max_length=255, min_length=1)
    data_inventory_id: int
    access_level: str = Field(max_length=50)  # read, write, delete, admin
    access_reason: str = Field(max_length=500)
    role_based: bool = Field(default=True)
    role_name: Optional[str] = Field(default=None, max_length=100)
    granted_by: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)


class EmployeeDataAccessCreate(EmployeeDataAccessBase):
    """Schema for creating new employee data access records."""

    pass


class EmployeeDataAccessUpdate(SQLModel):
    """Schema for updating employee data access - all fields optional."""

    access_level: Optional[str] = Field(default=None, max_length=50)
    access_reason: Optional[str] = Field(default=None, max_length=500)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class EmployeeDataAccessPublic(EmployeeDataAccessBase):
    """Schema for employee data access responses."""

    id: int
    granted_at: datetime
    created_at: datetime
    updated_at: datetime


class DataRetentionBase(SQLModel):
    """Base schema for data retention tracking with shared fields."""

    data_inventory_id: int
    record_id: str = Field(max_length=255)
    data_created_at: datetime
    retention_expires_at: datetime
    retention_status: str = Field(default="active", max_length=50)
    marked_for_deletion: bool = Field(default=False)
    deletion_reason: Optional[str] = Field(default=None, max_length=500)
    data_subject_id: Optional[str] = Field(default=None, max_length=255)


class DataRetentionCreate(SQLModel):
    """Schema for creating data retention records."""

    data_inventory_id: int
    record_id: str = Field(max_length=255)
    data_created_at: datetime
    data_subject_id: Optional[str] = Field(default=None, max_length=255)


class DataRetentionUpdate(SQLModel):
    """Schema for updating data retention records."""

    retention_status: Optional[str] = Field(default=None, max_length=50)
    marked_for_deletion: Optional[bool] = None
    deletion_reason: Optional[str] = Field(default=None, max_length=500)


class DataRetentionPublic(DataRetentionBase):
    """Schema for data retention responses."""

    id: int
    data_last_accessed: Optional[datetime] = None
    marked_for_deletion_at: Optional[datetime] = None
    deletion_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class EmployeeDataAboutMe(SQLModel):
    """Schema for employee's personal data summary (GDPR Article 15 - Right of Access)."""

    employee_id: str
    data_categories: list[str]
    total_records: int
    last_access_date: Optional[datetime] = None
    data_retention_summary: dict
    access_granted_at: datetime


class EmployeeAccessControls(SQLModel):
    """Schema showing what data an employee can access and why."""

    employee_id: str
    accessible_data_categories: list[dict]  # {id, name, access_level, reason}
    total_access_entries: int
    role_based_accesses: int
    direct_accesses: int


class DataRetentionReport(SQLModel):
    """Schema for data retention report showing what needs deletion."""

    total_records_tracked: int
    active_records: int
    expiring_soon: int  # Within 30 days
    expired_records: int
    marked_for_deletion: int
    recently_deleted: int
    retention_items: list[dict]  # List of retention records needing action
