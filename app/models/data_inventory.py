"""
Data Inventory database models.
Defines the SQLModel table structures for data inventory and categories.
Implements GDPR Article 30 - Records of Processing Activities.
"""

from sqlmodel import Field, SQLModel
from datetime import datetime


class DataCategory(SQLModel, table=True):
    """
    Data Category table model.
    Represents different categories of data in the system.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=255, nullable=False, unique=True)
    description: str | None = Field(default=None, max_length=1000)
    sensitivity_level: str = Field(
        default="low",
        max_length=50,
        nullable=False,
    )  # low, medium, high, critical
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DataInventory(SQLModel, table=True):
    """
    Data Inventory table model.
    Represents all data stored in the system with processing details.
    Compliant with GDPR Article 30 - Records of Processing Activities.
    """

    id: int | None = Field(default=None, primary_key=True)
    data_name: str = Field(index=True, max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=2000)
    category_id: int = Field(foreign_key="datacategory.id", nullable=False)
    data_type: str = Field(
        max_length=100, nullable=False
    )  # personal, sensitive, employment, health, etc.
    storage_location: str = Field(
        max_length=255, nullable=False
    )  # database name, table name, etc.
    purpose_of_processing: str = Field(
        max_length=1000, nullable=False
    )  # Why we collect this data
    legal_basis: str = Field(
        max_length=500, nullable=False
    )  # Consent, Contract, Legal Obligation, etc.
    retention_days: int = Field(default=365, nullable=False, ge=1)
    retention_policy: str = Field(
        max_length=1000, nullable=True
    )  # Description of retention policy
    data_subjects: str = Field(
        max_length=500, nullable=False
    )  # Who this data is about (e.g., employees, contractors)
    recipients: str | None = Field(
        default=None, max_length=1000
    )  # Who has access to this data
    third_party_sharing: bool = Field(default=False)
    third_party_recipients: str | None = Field(
        default=None, max_length=1000
    )  # If shared, with whom
    encryption_status: str = Field(
        default="encrypted", max_length=50, nullable=False
    )  # encrypted, not_encrypted
    access_control_level: str = Field(
        default="restricted", max_length=50, nullable=False
    )  # public, internal, restricted, confidential
    processing_system: str = Field(
        max_length=255, nullable=False
    )  # Which system processes this data
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_retention_check: datetime | None = Field(default=None)
