"""
Kafka Event Consumers and Handlers for Compliance Service.

Handles incoming events from other services to track data processing activities
and maintain data inventory for GDPR compliance.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.cache import get_cache_service
from app.core.config import settings
from app.core.database import engine
from app.core.events import (
    EventEnvelope,
    create_compliance_audit_event,
)
from app.core.kafka import KafkaConsumerService, get_producer, publish_compliance_event
from app.core.logging import get_logger
from app.core.topics import KafkaTopics
from app.models.data_inventory import DataCategory, DataInventory
from app.models.employee_data_access import DataRetention, EmployeeDataAccess

logger = get_logger(__name__)


# ==========================================
# Data Inventory Mapping
# ==========================================

# Maps event types to data inventory information
DATA_INVENTORY_MAPPING = {
    # User events
    "user-created": {
        "data_name": "User Account Data",
        "data_type": "personal",
        "storage_location": "user_management_service.users",
        "purpose": "User authentication and identification",
        "legal_basis": "Contract - Employment agreement",
    },
    "user-updated": {
        "data_name": "User Account Data",
        "data_type": "personal",
        "storage_location": "user_management_service.users",
        "purpose": "User authentication and identification",
        "legal_basis": "Contract - Employment agreement",
    },
    # Employee events
    "employee-created": {
        "data_name": "Employee Personal Data",
        "data_type": "personal",
        "storage_location": "employee_management_service.employees",
        "purpose": "Human resource management and employment record keeping",
        "legal_basis": "Contract - Employment agreement",
    },
    "employee-updated": {
        "data_name": "Employee Personal Data",
        "data_type": "personal",
        "storage_location": "employee_management_service.employees",
        "purpose": "Human resource management and employment record keeping",
        "legal_basis": "Contract - Employment agreement",
    },
    "employee-salary-updated": {
        "data_name": "Employee Salary Data",
        "data_type": "sensitive",
        "storage_location": "employee_management_service.salaries",
        "purpose": "Payroll processing and compensation management",
        "legal_basis": "Contract - Employment agreement",
    },
    "employee-salary-increment": {
        "data_name": "Employee Salary Data",
        "data_type": "sensitive",
        "storage_location": "employee_management_service.salaries",
        "purpose": "Payroll processing and compensation management",
        "legal_basis": "Contract - Employment agreement",
    },
    # Attendance events
    "attendance-checkin": {
        "data_name": "Attendance Records",
        "data_type": "employment",
        "storage_location": "attendance_management_service.attendance",
        "purpose": "Time tracking and work hour monitoring",
        "legal_basis": "Contract - Employment agreement",
    },
    "attendance-checkout": {
        "data_name": "Attendance Records",
        "data_type": "employment",
        "storage_location": "attendance_management_service.attendance",
        "purpose": "Time tracking and work hour monitoring",
        "legal_basis": "Contract - Employment agreement",
    },
    # Leave events
    "leave-requested": {
        "data_name": "Leave Records",
        "data_type": "employment",
        "storage_location": "leave_management_service.leaves",
        "purpose": "Leave management and absence tracking",
        "legal_basis": "Contract - Employment agreement",
    },
    "leave-approved": {
        "data_name": "Leave Records",
        "data_type": "employment",
        "storage_location": "leave_management_service.leaves",
        "purpose": "Leave management and absence tracking",
        "legal_basis": "Contract - Employment agreement",
    },
    # Notification events
    "notification-sent": {
        "data_name": "Communication Records",
        "data_type": "operational",
        "storage_location": "notification_service.notifications",
        "purpose": "Communication tracking and audit",
        "legal_basis": "Legitimate Interest - Business operations",
    },
}


# ==========================================
# Event Handlers
# ==========================================


def handle_user_created_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle user created events - track new personal data collection."""
    logger.info(f"Processing user-created event from {topic}")

    cache = get_cache_service()

    # Extract event ID for deduplication
    event_id = event_data.get("event_id") or event_data.get("payload", {}).get(
        "user_id"
    )
    if event_id and cache.is_duplicate_event(f"user-created:{event_id}"):
        logger.debug(f"Duplicate event skipped: {event_id}")
        return

    payload = event_data.get("payload", event_data)
    user_id = payload.get("user_id") or payload.get("id")

    if not user_id:
        logger.warning("User created event missing user_id")
        return

    try:
        with Session(engine) as session:
            # Find or create data inventory entry for user data
            inventory = _get_or_create_data_inventory(
                session,
                data_name="User Account Data",
                data_type="personal",
                storage_location="user_management_service.users",
                purpose="User authentication and identification",
                legal_basis="Contract - Employment agreement",
            )

            # Create retention tracking record
            _create_retention_record(
                session,
                inventory_id=inventory.id,
                record_id=user_id,
                data_subject_id=user_id,
            )

            session.commit()

        # Mark event as processed
        if event_id:
            cache.mark_event_processed(f"user-created:{event_id}")

        # Invalidate relevant caches
        cache.invalidate_inventory_cache()
        cache.invalidate_employee_data_cache(user_id)

        # Increment counter
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"data_collected:{today}")

        logger.info(f"User data tracking created for user {user_id}")

    except Exception as e:
        logger.error(f"Error processing user-created event: {e}")


def handle_user_updated_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle user updated events - track data modifications."""
    logger.info(f"Processing user-updated event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    user_id = payload.get("user_id") or payload.get("id")

    if not user_id:
        logger.warning("User updated event missing user_id")
        return

    try:
        with Session(engine) as session:
            # Update last accessed time for retention tracking
            _update_retention_access(session, record_id=user_id)
            session.commit()

        # Invalidate cache
        cache.invalidate_employee_data_cache(user_id)

        logger.info(f"User data access updated for user {user_id}")

    except Exception as e:
        logger.error(f"Error processing user-updated event: {e}")


def handle_user_deleted_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle user deleted events - track data deletion."""
    logger.info(f"Processing user-deleted event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    user_id = payload.get("user_id") or payload.get("id")
    deletion_reason = payload.get("deletion_reason", "User account deletion")

    if not user_id:
        logger.warning("User deleted event missing user_id")
        return

    try:
        with Session(engine) as session:
            # Mark retention record as deleted
            _mark_retention_deleted(
                session,
                record_id=user_id,
                deletion_reason=deletion_reason,
            )
            session.commit()

        # Invalidate caches
        cache.invalidate_employee_data_cache(user_id)
        cache.invalidate_retention_cache()

        # Increment deletion counter
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"data_deleted:{today}")

        logger.info(f"User data deletion tracked for user {user_id}")

        # Publish compliance event
        _publish_data_deleted_event(user_id, "user", deletion_reason)

    except Exception as e:
        logger.error(f"Error processing user-deleted event: {e}")


def handle_employee_created_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle employee created events - track new employee data collection."""
    logger.info(f"Processing employee-created event from {topic}")

    cache = get_cache_service()

    event_id = event_data.get("event_id") or event_data.get("payload", {}).get(
        "employee_id"
    )
    if event_id and cache.is_duplicate_event(f"employee-created:{event_id}"):
        logger.debug(f"Duplicate event skipped: {event_id}")
        return

    payload = event_data.get("payload", event_data)
    employee_id = payload.get("employee_id") or payload.get("id")
    user_id = payload.get("user_id")

    if not employee_id:
        logger.warning("Employee created event missing employee_id")
        return

    try:
        with Session(engine) as session:
            # Create data inventory entry for employee data
            inventory = _get_or_create_data_inventory(
                session,
                data_name="Employee Personal Data",
                data_type="personal",
                storage_location="employee_management_service.employees",
                purpose="Human resource management and employment record keeping",
                legal_basis="Contract - Employment agreement",
            )

            # Create retention tracking record
            _create_retention_record(
                session,
                inventory_id=inventory.id,
                record_id=employee_id,
                data_subject_id=user_id or employee_id,
            )

            session.commit()

        if event_id:
            cache.mark_event_processed(f"employee-created:{event_id}")

        cache.invalidate_inventory_cache()
        if user_id:
            cache.invalidate_employee_data_cache(user_id)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"data_collected:{today}")

        logger.info(f"Employee data tracking created for employee {employee_id}")

    except Exception as e:
        logger.error(f"Error processing employee-created event: {e}")


def handle_employee_updated_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle employee updated events - track data modifications."""
    logger.info(f"Processing employee-updated event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    employee_id = payload.get("employee_id") or payload.get("id")
    user_id = payload.get("user_id")

    if not employee_id:
        logger.warning("Employee updated event missing employee_id")
        return

    try:
        with Session(engine) as session:
            _update_retention_access(session, record_id=employee_id)
            session.commit()

        if user_id:
            cache.invalidate_employee_data_cache(user_id)

        logger.info(f"Employee data access updated for employee {employee_id}")

    except Exception as e:
        logger.error(f"Error processing employee-updated event: {e}")


def handle_employee_terminated_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle employee terminated events - start retention countdown."""
    logger.info(f"Processing employee-terminated event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    employee_id = payload.get("employee_id") or payload.get("id")
    user_id = payload.get("user_id")

    if not employee_id:
        logger.warning("Employee terminated event missing employee_id")
        return

    try:
        with Session(engine) as session:
            # Update retention status to indicate termination
            # Data can be retained for legal compliance period
            statement = select(DataRetention).where(
                DataRetention.record_id == employee_id
            )
            retention_records = session.exec(statement).all()

            for record in retention_records:
                record.retention_status = "termination_retention"
                record.updated_at = datetime.utcnow()
                session.add(record)

            session.commit()

        cache.invalidate_retention_cache()
        if user_id:
            cache.invalidate_employee_data_cache(user_id)

        logger.info(
            f"Employee termination retention started for employee {employee_id}"
        )

    except Exception as e:
        logger.error(f"Error processing employee-terminated event: {e}")


def handle_attendance_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle attendance events - track time and location data collection."""
    logger.info(f"Processing attendance event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    employee_id = payload.get("employee_id")
    attendance_id = payload.get("attendance_id") or payload.get("id")

    if not employee_id:
        logger.warning("Attendance event missing employee_id")
        return

    try:
        with Session(engine) as session:
            inventory = _get_or_create_data_inventory(
                session,
                data_name="Attendance Records",
                data_type="employment",
                storage_location="attendance_management_service.attendance",
                purpose="Time tracking and work hour monitoring",
                legal_basis="Contract - Employment agreement",
            )

            if attendance_id:
                _create_retention_record(
                    session,
                    inventory_id=inventory.id,
                    record_id=attendance_id,
                    data_subject_id=employee_id,
                )

            session.commit()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"attendance_records:{today}")

        logger.info(f"Attendance data tracked for employee {employee_id}")

    except Exception as e:
        logger.error(f"Error processing attendance event: {e}")


def handle_leave_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle leave events - track leave request data."""
    logger.info(f"Processing leave event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    employee_id = payload.get("employee_id")
    leave_id = payload.get("leave_id") or payload.get("id")

    if not employee_id:
        logger.warning("Leave event missing employee_id")
        return

    try:
        with Session(engine) as session:
            inventory = _get_or_create_data_inventory(
                session,
                data_name="Leave Records",
                data_type="employment",
                storage_location="leave_management_service.leaves",
                purpose="Leave management and absence tracking",
                legal_basis="Contract - Employment agreement",
            )

            if leave_id:
                _create_retention_record(
                    session,
                    inventory_id=inventory.id,
                    record_id=leave_id,
                    data_subject_id=employee_id,
                )

            session.commit()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"leave_records:{today}")

        logger.info(f"Leave data tracked for employee {employee_id}")

    except Exception as e:
        logger.error(f"Error processing leave event: {e}")


def handle_notification_event(event_data: dict[str, Any], topic: str) -> None:
    """Handle notification events - track communication records."""
    logger.info(f"Processing notification event from {topic}")

    cache = get_cache_service()
    payload = event_data.get("payload", event_data)
    recipient_id = payload.get("recipient_id") or payload.get("employee_id")
    notification_id = payload.get("notification_id") or payload.get("id")

    if not recipient_id:
        logger.warning("Notification event missing recipient_id")
        return

    try:
        with Session(engine) as session:
            inventory = _get_or_create_data_inventory(
                session,
                data_name="Communication Records",
                data_type="operational",
                storage_location="notification_service.notifications",
                purpose="Communication tracking and audit",
                legal_basis="Legitimate Interest - Business operations",
            )

            if notification_id:
                _create_retention_record(
                    session,
                    inventory_id=inventory.id,
                    record_id=notification_id,
                    data_subject_id=recipient_id,
                )

            session.commit()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cache.increment_counter(f"notifications_tracked:{today}")

        logger.info(f"Notification data tracked for recipient {recipient_id}")

    except Exception as e:
        logger.error(f"Error processing notification event: {e}")


def handle_generic_event(event_data: dict[str, Any], topic: str) -> None:
    """Generic handler for unmapped events - logs for review."""
    logger.info(f"Received event on topic {topic} (generic handler)")

    event_type = event_data.get("event_type", topic)

    # Check if we have mapping for this event type
    if event_type in DATA_INVENTORY_MAPPING:
        logger.debug(f"Event type {event_type} has mapping, processing...")
        mapping = DATA_INVENTORY_MAPPING[event_type]

        payload = event_data.get("payload", event_data)
        record_id = (
            payload.get("id")
            or payload.get("user_id")
            or payload.get("employee_id")
            or payload.get("attendance_id")
            or payload.get("leave_id")
        )

        if record_id:
            try:
                with Session(engine) as session:
                    inventory = _get_or_create_data_inventory(
                        session,
                        data_name=mapping["data_name"],
                        data_type=mapping["data_type"],
                        storage_location=mapping["storage_location"],
                        purpose=mapping["purpose"],
                        legal_basis=mapping["legal_basis"],
                    )

                    _create_retention_record(
                        session,
                        inventory_id=inventory.id,
                        record_id=str(record_id),
                        data_subject_id=payload.get("user_id")
                        or payload.get("employee_id"),
                    )

                    session.commit()

            except Exception as e:
                logger.error(f"Error in generic handler for {topic}: {e}")
    else:
        logger.debug(f"No mapping for event type {event_type} from topic {topic}")


# ==========================================
# Helper Functions
# ==========================================


def _get_or_create_data_inventory(
    session: Session,
    data_name: str,
    data_type: str,
    storage_location: str,
    purpose: str,
    legal_basis: str,
) -> DataInventory:
    """Get existing or create new data inventory entry."""
    statement = select(DataInventory).where(
        DataInventory.data_name == data_name,
        DataInventory.storage_location == storage_location,
    )
    inventory = session.exec(statement).first()

    if inventory:
        return inventory

    # Get or create default category
    category = _get_or_create_category(session, data_type)

    inventory = DataInventory(
        data_name=data_name,
        data_type=data_type,
        category_id=category.id,
        storage_location=storage_location,
        purpose_of_processing=purpose,
        legal_basis=legal_basis,
        retention_days=settings.DEFAULT_RETENTION_DAYS,
        data_subjects="employees",
        processing_system="HRMS",
        encryption_status="encrypted",
        access_control_level="restricted",
    )
    session.add(inventory)
    session.flush()

    return inventory


def _get_or_create_category(session: Session, data_type: str) -> DataCategory:
    """Get existing or create new data category."""
    # Map data types to categories
    category_mapping = {
        "personal": ("Personal Data", "high"),
        "sensitive": ("Sensitive Data", "critical"),
        "employment": ("Employment Data", "medium"),
        "operational": ("Operational Data", "low"),
    }

    category_name, sensitivity = category_mapping.get(
        data_type, ("Other Data", "medium")
    )

    statement = select(DataCategory).where(DataCategory.name == category_name)
    category = session.exec(statement).first()

    if category:
        return category

    category = DataCategory(
        name=category_name,
        description=f"Category for {data_type} data",
        sensitivity_level=sensitivity,
    )
    session.add(category)
    session.flush()

    return category


def _create_retention_record(
    session: Session,
    inventory_id: int,
    record_id: str,
    data_subject_id: Optional[str] = None,
) -> DataRetention:
    """Create data retention tracking record."""
    # Check if already exists
    statement = select(DataRetention).where(
        DataRetention.data_inventory_id == inventory_id,
        DataRetention.record_id == record_id,
    )
    existing = session.exec(statement).first()

    if existing:
        existing.data_last_accessed = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        return existing

    # Get retention days from inventory
    inventory = session.get(DataInventory, inventory_id)
    retention_days = (
        inventory.retention_days if inventory else settings.DEFAULT_RETENTION_DAYS
    )

    now = datetime.utcnow()
    retention = DataRetention(
        data_inventory_id=inventory_id,
        record_id=record_id,
        data_created_at=now,
        data_last_accessed=now,
        retention_expires_at=now + timedelta(days=retention_days),
        retention_status="active",
        data_subject_id=data_subject_id,
    )
    session.add(retention)

    return retention


def _update_retention_access(session: Session, record_id: str) -> None:
    """Update last accessed time for retention records."""
    statement = select(DataRetention).where(DataRetention.record_id == record_id)
    records = session.exec(statement).all()

    now = datetime.utcnow()
    for record in records:
        record.data_last_accessed = now
        record.updated_at = now
        session.add(record)


def _mark_retention_deleted(
    session: Session,
    record_id: str,
    deletion_reason: str,
) -> None:
    """Mark retention records as deleted."""
    statement = select(DataRetention).where(DataRetention.record_id == record_id)
    records = session.exec(statement).all()

    now = datetime.utcnow()
    for record in records:
        record.retention_status = "deleted"
        record.marked_for_deletion = True
        record.marked_for_deletion_at = now
        record.deletion_completed_at = now
        record.deletion_reason = deletion_reason
        record.updated_at = now
        session.add(record)


def _publish_data_deleted_event(
    record_id: str,
    data_type: str,
    deletion_reason: str,
) -> None:
    """Publish data deletion event for audit."""
    try:
        from app.core.events import create_data_deleted_event

        event = EventEnvelope.create(
            event_type="compliance-data-deleted",
            payload={
                "record_id": record_id,
                "data_type": data_type,
                "deletion_reason": deletion_reason,
                "deleted_at": datetime.utcnow().isoformat(),
                "deleted_by": "system",
            },
        )

        producer = get_producer()
        producer.publish_event(KafkaTopics.COMPLIANCE_DATA_DELETED, event)

    except Exception as e:
        logger.error(f"Failed to publish data deleted event: {e}")


# ==========================================
# Handler Registration
# ==========================================

# Topic to handler mapping
TOPIC_HANDLERS = {
    # User events
    KafkaTopics.USER_CREATED: handle_user_created_event,
    KafkaTopics.USER_UPDATED: handle_user_updated_event,
    KafkaTopics.USER_DELETED: handle_user_deleted_event,
    KafkaTopics.USER_SUSPENDED: handle_user_updated_event,
    KafkaTopics.USER_ACTIVATED: handle_user_updated_event,
    KafkaTopics.USER_ROLE_CHANGED: handle_user_updated_event,
    KafkaTopics.USER_ONBOARDING_INITIATED: handle_user_created_event,
    KafkaTopics.USER_ONBOARDING_COMPLETED: handle_user_updated_event,
    KafkaTopics.USER_ONBOARDING_FAILED: handle_generic_event,
    # Employee events
    KafkaTopics.EMPLOYEE_CREATED: handle_employee_created_event,
    KafkaTopics.EMPLOYEE_UPDATED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_DELETED: handle_user_deleted_event,
    KafkaTopics.EMPLOYEE_TERMINATED: handle_employee_terminated_event,
    KafkaTopics.EMPLOYEE_PROMOTED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_TRANSFERRED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_SALARY_UPDATED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_SALARY_INCREMENT: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_CONTRACT_STARTED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_CONTRACT_RENEWED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_CONTRACT_ENDED: handle_employee_terminated_event,
    KafkaTopics.EMPLOYEE_PROBATION_STARTED: handle_employee_updated_event,
    KafkaTopics.EMPLOYEE_PROBATION_COMPLETED: handle_employee_updated_event,
    # Attendance events
    KafkaTopics.ATTENDANCE_CHECKIN: handle_attendance_event,
    KafkaTopics.ATTENDANCE_CHECKOUT: handle_attendance_event,
    KafkaTopics.ATTENDANCE_UPDATED: handle_attendance_event,
    # Leave events
    KafkaTopics.LEAVE_REQUESTED: handle_leave_event,
    KafkaTopics.LEAVE_APPROVED: handle_leave_event,
    KafkaTopics.LEAVE_REJECTED: handle_leave_event,
    KafkaTopics.LEAVE_CANCELLED: handle_leave_event,
    # Notification events
    KafkaTopics.NOTIFICATION_SENT: handle_notification_event,
    KafkaTopics.NOTIFICATION_FAILED: handle_notification_event,
}


def register_all_handlers(consumer: KafkaConsumerService) -> None:
    """Register all event handlers with the consumer."""
    for topic, handler in TOPIC_HANDLERS.items():
        consumer.register_handler(topic, handler)

    logger.info(f"Registered {len(TOPIC_HANDLERS)} event handlers")


def start_consumer() -> KafkaConsumerService:
    """Start the Kafka consumer with all handlers."""
    from app.core.kafka import get_consumer

    consumer = get_consumer(topics=KafkaTopics.all_subscribed_topics())
    register_all_handlers(consumer)
    consumer.start()

    return consumer
