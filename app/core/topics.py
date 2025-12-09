"""
Kafka Topic Definitions for Compliance Service.

This service subscribes to topics from multiple services to track data processing
activities and maintain data inventory for GDPR compliance.
Topic naming follows the pattern: <domain>-<event-type>
"""


class KafkaTopics:
    """
    Central registry of all Kafka topics consumed and published by the Compliance Service.
    Topics are organized by source service for clarity.
    """

    # ==========================================
    # User Management Service Topics (Subscribe)
    # ==========================================

    # User Lifecycle Events - Track personal data processing
    USER_CREATED = "user-created"
    USER_UPDATED = "user-updated"
    USER_DELETED = "user-deleted"
    USER_SUSPENDED = "user-suspended"
    USER_ACTIVATED = "user-activated"
    USER_ROLE_CHANGED = "user-role-changed"

    # Onboarding Events - Track new data collection
    USER_ONBOARDING_INITIATED = "user-onboarding-initiated"
    USER_ONBOARDING_COMPLETED = "user-onboarding-completed"
    USER_ONBOARDING_FAILED = "user-onboarding-failed"

    # ==========================================
    # Employee Management Service Topics (Subscribe)
    # ==========================================

    # Employee Lifecycle Events - Track employment data processing
    EMPLOYEE_CREATED = "employee-created"
    EMPLOYEE_UPDATED = "employee-updated"
    EMPLOYEE_DELETED = "employee-deleted"
    EMPLOYEE_TERMINATED = "employee-terminated"
    EMPLOYEE_PROMOTED = "employee-promoted"
    EMPLOYEE_TRANSFERRED = "employee-transferred"

    # Salary Events - Track sensitive financial data
    EMPLOYEE_SALARY_UPDATED = "employee-salary-updated"
    EMPLOYEE_SALARY_INCREMENT = "employee-salary-increment"

    # Contract Events - Track employment contracts
    EMPLOYEE_CONTRACT_STARTED = "employee-contract-started"
    EMPLOYEE_CONTRACT_RENEWED = "employee-contract-renewed"
    EMPLOYEE_CONTRACT_ENDED = "employee-contract-ended"

    # Probation Events
    EMPLOYEE_PROBATION_STARTED = "employee-probation-started"
    EMPLOYEE_PROBATION_COMPLETED = "employee-probation-completed"

    # ==========================================
    # Attendance Management Service Topics (Subscribe)
    # ==========================================

    # Attendance Events - Track time and location data
    ATTENDANCE_CHECKIN = "attendance-checkin"
    ATTENDANCE_CHECKOUT = "attendance-checkout"
    ATTENDANCE_UPDATED = "attendance-updated"

    # ==========================================
    # Leave Management Service Topics (Subscribe)
    # ==========================================

    # Leave Events - Track absence data
    LEAVE_REQUESTED = "leave-requested"
    LEAVE_APPROVED = "leave-approved"
    LEAVE_REJECTED = "leave-rejected"
    LEAVE_CANCELLED = "leave-cancelled"

    # ==========================================
    # Notification Service Topics (Subscribe)
    # ==========================================

    # Notification Events - Track communication data
    NOTIFICATION_SENT = "notification-sent"
    NOTIFICATION_FAILED = "notification-failed"

    # ==========================================
    # Compliance Service Own Topics (Publishing)
    # ==========================================

    # Data Inventory Events
    COMPLIANCE_DATA_INVENTORY_UPDATED = "compliance-data-inventory-updated"
    COMPLIANCE_DATA_CATEGORY_CREATED = "compliance-data-category-created"
    COMPLIANCE_DATA_CATEGORY_UPDATED = "compliance-data-category-updated"

    # Retention Events
    COMPLIANCE_RETENTION_CHECK = "compliance-retention-check"
    COMPLIANCE_RETENTION_WARNING = "compliance-retention-warning"
    COMPLIANCE_DATA_EXPIRED = "compliance-data-expired"
    COMPLIANCE_DATA_DELETED = "compliance-data-deleted"

    # Data Subject Rights Events (GDPR Article 15, 17, 20)
    COMPLIANCE_DATA_ACCESS_REQUEST = "compliance-data-access-request"
    COMPLIANCE_DATA_DELETION_REQUEST = "compliance-data-deletion-request"
    COMPLIANCE_DATA_EXPORT_REQUEST = "compliance-data-export-request"

    # Access Control Events
    COMPLIANCE_ACCESS_GRANTED = "compliance-access-granted"
    COMPLIANCE_ACCESS_REVOKED = "compliance-access-revoked"

    # Audit Events
    AUDIT_COMPLIANCE_ACTION = "audit-compliance-action"

    @classmethod
    def all_subscribed_topics(cls) -> list[str]:
        """Return list of all topics this service subscribes to."""
        return (
            cls.user_lifecycle_topics()
            + cls.employee_lifecycle_topics()
            + cls.attendance_topics()
            + cls.leave_topics()
            + cls.notification_topics()
        )

    @classmethod
    def user_lifecycle_topics(cls) -> list[str]:
        """Return list of user lifecycle topics to subscribe to."""
        return [
            cls.USER_CREATED,
            cls.USER_UPDATED,
            cls.USER_DELETED,
            cls.USER_SUSPENDED,
            cls.USER_ACTIVATED,
            cls.USER_ROLE_CHANGED,
            cls.USER_ONBOARDING_INITIATED,
            cls.USER_ONBOARDING_COMPLETED,
            cls.USER_ONBOARDING_FAILED,
        ]

    @classmethod
    def employee_lifecycle_topics(cls) -> list[str]:
        """Return list of employee lifecycle topics to subscribe to."""
        return [
            cls.EMPLOYEE_CREATED,
            cls.EMPLOYEE_UPDATED,
            cls.EMPLOYEE_DELETED,
            cls.EMPLOYEE_TERMINATED,
            cls.EMPLOYEE_PROMOTED,
            cls.EMPLOYEE_TRANSFERRED,
            cls.EMPLOYEE_SALARY_UPDATED,
            cls.EMPLOYEE_SALARY_INCREMENT,
            cls.EMPLOYEE_CONTRACT_STARTED,
            cls.EMPLOYEE_CONTRACT_RENEWED,
            cls.EMPLOYEE_CONTRACT_ENDED,
            cls.EMPLOYEE_PROBATION_STARTED,
            cls.EMPLOYEE_PROBATION_COMPLETED,
        ]

    @classmethod
    def attendance_topics(cls) -> list[str]:
        """Return list of attendance topics to subscribe to."""
        return [
            cls.ATTENDANCE_CHECKIN,
            cls.ATTENDANCE_CHECKOUT,
            cls.ATTENDANCE_UPDATED,
        ]

    @classmethod
    def leave_topics(cls) -> list[str]:
        """Return list of leave topics to subscribe to."""
        return [
            cls.LEAVE_REQUESTED,
            cls.LEAVE_APPROVED,
            cls.LEAVE_REJECTED,
            cls.LEAVE_CANCELLED,
        ]

    @classmethod
    def notification_topics(cls) -> list[str]:
        """Return list of notification topics to subscribe to."""
        return [
            cls.NOTIFICATION_SENT,
            cls.NOTIFICATION_FAILED,
        ]

    @classmethod
    def publishing_topics(cls) -> list[str]:
        """Return list of topics this service publishes to."""
        return [
            cls.COMPLIANCE_DATA_INVENTORY_UPDATED,
            cls.COMPLIANCE_DATA_CATEGORY_CREATED,
            cls.COMPLIANCE_DATA_CATEGORY_UPDATED,
            cls.COMPLIANCE_RETENTION_CHECK,
            cls.COMPLIANCE_RETENTION_WARNING,
            cls.COMPLIANCE_DATA_EXPIRED,
            cls.COMPLIANCE_DATA_DELETED,
            cls.COMPLIANCE_DATA_ACCESS_REQUEST,
            cls.COMPLIANCE_DATA_DELETION_REQUEST,
            cls.COMPLIANCE_DATA_EXPORT_REQUEST,
            cls.COMPLIANCE_ACCESS_GRANTED,
            cls.COMPLIANCE_ACCESS_REVOKED,
            cls.AUDIT_COMPLIANCE_ACTION,
        ]

    @classmethod
    def all_topics(cls) -> list[str]:
        """Return all topics (subscribed + published)."""
        return cls.all_subscribed_topics() + cls.publishing_topics()
