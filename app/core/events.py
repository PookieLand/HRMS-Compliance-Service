"""
Kafka Event Models for Compliance Service.

Defines Pydantic models for events consumed and published by the Compliance Service.
Uses event envelope pattern for consistent event structure across services.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventMetadata(BaseModel):
    """Metadata attached to every event for tracing and debugging."""

    source_service: str = "compliance-service"
    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    causation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"
    environment: str = "production"


class EventEnvelope(BaseModel):
    """
    Standard event envelope for all Kafka messages.
    Provides consistent structure for routing and processing.
    """

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any]
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ) -> "EventEnvelope":
        """Factory method to create an event envelope."""
        metadata = EventMetadata(
            source_service="compliance-service",
            correlation_id=correlation_id or uuid4().hex,
            causation_id=causation_id,
        )
        return cls(
            event_type=event_type,
            payload=payload,
            metadata=metadata,
        )


# ==========================================
# Incoming Events (Consumed)
# ==========================================


class UserCreatedEvent(BaseModel):
    """Event received when a new user is created."""

    user_id: str
    email: str
    role: str
    created_at: datetime
    created_by: Optional[str] = None
    additional_data: Optional[dict[str, Any]] = None


class UserUpdatedEvent(BaseModel):
    """Event received when a user is updated."""

    user_id: str
    updated_fields: list[str]
    updated_at: datetime
    updated_by: Optional[str] = None
    old_values: Optional[dict[str, Any]] = None
    new_values: Optional[dict[str, Any]] = None


class UserDeletedEvent(BaseModel):
    """Event received when a user is deleted."""

    user_id: str
    deleted_at: datetime
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None


class EmployeeCreatedEvent(BaseModel):
    """Event received when a new employee is created."""

    employee_id: str
    user_id: str
    first_name: str
    last_name: str
    email: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: str  # permanent, contract
    hire_date: datetime
    created_at: datetime
    created_by: Optional[str] = None


class EmployeeUpdatedEvent(BaseModel):
    """Event received when an employee is updated."""

    employee_id: str
    updated_fields: list[str]
    updated_at: datetime
    updated_by: Optional[str] = None
    old_values: Optional[dict[str, Any]] = None
    new_values: Optional[dict[str, Any]] = None


class EmployeeDeletedEvent(BaseModel):
    """Event received when an employee record is deleted."""

    employee_id: str
    deleted_at: datetime
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None


class EmployeeTerminatedEvent(BaseModel):
    """Event received when an employee is terminated."""

    employee_id: str
    termination_date: datetime
    termination_reason: Optional[str] = None
    terminated_by: Optional[str] = None


class AttendanceEvent(BaseModel):
    """Event received for attendance check-in/check-out."""

    attendance_id: str
    employee_id: str
    event_type: str  # checkin, checkout
    timestamp: datetime
    location: Optional[str] = None
    ip_address: Optional[str] = None


class LeaveEvent(BaseModel):
    """Event received for leave requests."""

    leave_id: str
    employee_id: str
    event_type: str  # requested, approved, rejected, cancelled
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None
    processed_by: Optional[str] = None


class NotificationEvent(BaseModel):
    """Event received when notifications are sent/failed."""

    notification_id: str
    recipient_id: str
    notification_type: str
    channel: str  # email, sms, push
    status: str  # sent, failed
    sent_at: datetime
    content_summary: Optional[str] = None


# ==========================================
# Outgoing Events (Published)
# ==========================================


class DataInventoryUpdatedEvent(BaseModel):
    """Event published when data inventory is updated."""

    data_inventory_id: int
    data_name: str
    data_type: str
    operation: str  # created, updated, deleted
    category_id: int
    storage_location: str
    retention_days: int
    updated_at: datetime
    updated_by: Optional[str] = None


class DataCategoryEvent(BaseModel):
    """Event published when a data category is created/updated."""

    category_id: int
    name: str
    sensitivity_level: str
    operation: str  # created, updated, deleted
    timestamp: datetime


class RetentionCheckEvent(BaseModel):
    """Event published when retention check is performed."""

    check_id: str = Field(default_factory=lambda: uuid4().hex)
    check_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_records_checked: int
    expiring_soon_count: int
    expired_count: int
    deleted_count: int


class RetentionWarningEvent(BaseModel):
    """Event published when data is approaching retention limit."""

    data_retention_id: int
    data_inventory_id: int
    data_name: str
    record_id: str
    data_subject_id: Optional[str] = None
    retention_expires_at: datetime
    days_until_expiration: int
    warning_level: str  # low, medium, high, critical


class DataExpiredEvent(BaseModel):
    """Event published when data has expired."""

    data_retention_id: int
    data_inventory_id: int
    record_id: str
    data_subject_id: Optional[str] = None
    expired_at: datetime
    data_type: str


class DataDeletedEvent(BaseModel):
    """Event published when data is deleted for compliance."""

    data_retention_id: int
    data_inventory_id: int
    record_id: str
    data_subject_id: Optional[str] = None
    deleted_at: datetime = Field(default_factory=datetime.utcnow)
    deletion_reason: str
    deleted_by: str  # system or user_id


class DataAccessRequestEvent(BaseModel):
    """Event published for GDPR Article 15 - Right of Access requests."""

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    employee_id: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    requested_by: str
    status: str  # pending, completed, rejected
    data_categories: list[str]


class DataDeletionRequestEvent(BaseModel):
    """Event published for GDPR Article 17 - Right to Erasure requests."""

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    employee_id: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    requested_by: str
    status: str  # pending, processing, completed, rejected
    deletion_scope: list[str]  # Which data categories to delete
    rejection_reason: Optional[str] = None


class DataExportRequestEvent(BaseModel):
    """Event published for GDPR Article 20 - Right to Data Portability requests."""

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    employee_id: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    requested_by: str
    status: str  # pending, processing, completed
    export_format: str  # json, csv, pdf
    download_url: Optional[str] = None


class AccessControlEvent(BaseModel):
    """Event published when access control changes are made."""

    access_id: int
    employee_id: str
    data_inventory_id: int
    access_level: str  # read, write, delete, admin
    operation: str  # granted, revoked, updated
    granted_by: Optional[str] = None
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ComplianceAuditEvent(BaseModel):
    """Event published for compliance audit trail."""

    audit_id: str = Field(default_factory=lambda: uuid4().hex)
    action_type: str  # data_access, data_export, retention_check, access_grant, etc.
    actor_id: str
    actor_role: str
    target_type: str  # employee, data_inventory, data_category, etc.
    target_id: str
    action_details: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# ==========================================
# Helper Functions
# ==========================================


def create_compliance_audit_event(
    action_type: str,
    actor_id: str,
    actor_role: str,
    target_type: str,
    target_id: str,
    action_details: dict[str, Any],
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    """
    Create a compliance audit event envelope.

    Args:
        action_type: Type of compliance action performed
        actor_id: ID of the user performing the action
        actor_role: Role of the actor
        target_type: Type of entity being acted upon
        target_id: ID of the target entity
        action_details: Additional details about the action
        correlation_id: Optional correlation ID for tracing

    Returns:
        EventEnvelope ready to be published
    """
    audit_event = ComplianceAuditEvent(
        action_type=action_type,
        actor_id=actor_id,
        actor_role=actor_role,
        target_type=target_type,
        target_id=target_id,
        action_details=action_details,
    )

    return EventEnvelope.create(
        event_type="compliance-audit",
        payload=audit_event.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def create_retention_warning_event(
    data_retention_id: int,
    data_inventory_id: int,
    data_name: str,
    record_id: str,
    retention_expires_at: datetime,
    days_until_expiration: int,
    data_subject_id: Optional[str] = None,
) -> EventEnvelope:
    """
    Create a retention warning event envelope.

    Args:
        data_retention_id: ID of the retention record
        data_inventory_id: ID of the data inventory item
        data_name: Name of the data
        record_id: ID of the actual data record
        retention_expires_at: When retention expires
        days_until_expiration: Days until expiration
        data_subject_id: Optional ID of the data subject

    Returns:
        EventEnvelope ready to be published
    """
    # Determine warning level based on days
    if days_until_expiration <= 7:
        warning_level = "critical"
    elif days_until_expiration <= 14:
        warning_level = "high"
    elif days_until_expiration <= 21:
        warning_level = "medium"
    else:
        warning_level = "low"

    warning_event = RetentionWarningEvent(
        data_retention_id=data_retention_id,
        data_inventory_id=data_inventory_id,
        data_name=data_name,
        record_id=record_id,
        data_subject_id=data_subject_id,
        retention_expires_at=retention_expires_at,
        days_until_expiration=days_until_expiration,
        warning_level=warning_level,
    )

    return EventEnvelope.create(
        event_type="compliance-retention-warning",
        payload=warning_event.model_dump(mode="json"),
    )


def create_data_deleted_event(
    data_retention_id: int,
    data_inventory_id: int,
    record_id: str,
    deletion_reason: str,
    deleted_by: str,
    data_subject_id: Optional[str] = None,
) -> EventEnvelope:
    """
    Create a data deleted event envelope.

    Args:
        data_retention_id: ID of the retention record
        data_inventory_id: ID of the data inventory item
        record_id: ID of the deleted record
        deletion_reason: Reason for deletion
        deleted_by: Who initiated the deletion
        data_subject_id: Optional ID of the data subject

    Returns:
        EventEnvelope ready to be published
    """
    deleted_event = DataDeletedEvent(
        data_retention_id=data_retention_id,
        data_inventory_id=data_inventory_id,
        record_id=record_id,
        data_subject_id=data_subject_id,
        deletion_reason=deletion_reason,
        deleted_by=deleted_by,
    )

    return EventEnvelope.create(
        event_type="compliance-data-deleted",
        payload=deleted_event.model_dump(mode="json"),
    )
