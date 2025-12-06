"""
Data Inventory Pydantic schemas.
Defines request/response models for Data Inventory API endpoints.
Implements GDPR Article 30 - Records of Processing Activities.
"""

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class DataCategoryBase(SQLModel):
    """Base schema for data categories with shared fields."""

    name: str = Field(max_length=255, min_length=1)
    description: Optional[str] = Field(default=None, max_length=1000)
    sensitivity_level: str = Field(
        default="low", max_length=50
    )  # low, medium, high, critical


class DataCategoryCreate(DataCategoryBase):
    """Schema for creating a new data category."""

    pass


class DataCategoryPublic(DataCategoryBase):
    """Schema for data category responses."""

    id: int
    created_at: datetime
    updated_at: datetime


class DataInventoryBase(SQLModel):
    """Base schema for data inventory with shared fields."""

    data_name: str = Field(max_length=255, min_length=1)
    description: Optional[str] = Field(default=None, max_length=2000)
    category_id: int
    data_type: str = Field(max_length=100)  # personal, sensitive, employment, etc.
    storage_location: str = Field(max_length=255)
    purpose_of_processing: str = Field(max_length=1000)
    legal_basis: str = Field(max_length=500)
    retention_days: int = Field(default=365, ge=1)
    retention_policy: Optional[str] = Field(default=None, max_length=1000)
    data_subjects: str = Field(max_length=500)
    recipients: Optional[str] = Field(default=None, max_length=1000)
    third_party_sharing: bool = Field(default=False)
    third_party_recipients: Optional[str] = Field(default=None, max_length=1000)
    encryption_status: str = Field(default="encrypted", max_length=50)
    access_control_level: str = Field(default="restricted", max_length=50)
    processing_system: str = Field(max_length=255)


class DataInventoryCreate(DataInventoryBase):
    """Schema for creating new data inventory entries."""

    pass


class DataInventoryUpdate(SQLModel):
    """Schema for updating data inventory entries - all fields optional."""

    data_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    category_id: Optional[int] = None
    data_type: Optional[str] = Field(default=None, max_length=100)
    storage_location: Optional[str] = Field(default=None, max_length=255)
    purpose_of_processing: Optional[str] = Field(default=None, max_length=1000)
    legal_basis: Optional[str] = Field(default=None, max_length=500)
    retention_days: Optional[int] = Field(default=None, ge=1)
    retention_policy: Optional[str] = Field(default=None, max_length=1000)
    data_subjects: Optional[str] = Field(default=None, max_length=500)
    recipients: Optional[str] = Field(default=None, max_length=1000)
    third_party_sharing: Optional[bool] = None
    third_party_recipients: Optional[str] = Field(default=None, max_length=1000)
    encryption_status: Optional[str] = Field(default=None, max_length=50)
    access_control_level: Optional[str] = Field(default=None, max_length=50)
    processing_system: Optional[str] = Field(default=None, max_length=255)


class DataInventoryPublic(DataInventoryBase):
    """Schema for data inventory responses."""

    id: int
    created_at: datetime
    updated_at: datetime
    last_retention_check: Optional[datetime] = None


class DataInventorySummary(SQLModel):
    """Simplified schema for data inventory summary."""

    id: int
    data_name: str
    data_type: str
    category_id: int
    retention_days: int
    is_sensitive: bool = Field(default=False)
    access_control_level: str
    encryption_status: str
