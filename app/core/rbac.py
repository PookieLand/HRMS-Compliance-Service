"""
RBAC (Role-Based Access Control) for Compliance Service.

Implements access control rules for compliance data based on HRMS roles:
- HR_Admin: Full access to all compliance data and operations
- HR_Manager: Access to compliance data for employees below them
- manager: Limited access to team compliance information
- employee: Can only view their own data (data-about-me)

Per GDPR requirements, employees have the right to access their own data.
"""

from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


# Role hierarchy (higher number = higher privilege)
ROLE_HIERARCHY = {
    "HR_Admin": 4,
    "HR_Manager": 3,
    "manager": 2,
    "employee": 1,
}

# Roles that can access full compliance reports
COMPLIANCE_ADMIN_ROLES = {"HR_Admin"}

# Roles that can view data inventory
DATA_INVENTORY_ROLES = {"HR_Admin", "HR_Manager"}

# Roles that can view retention reports
RETENTION_REPORT_ROLES = {"HR_Admin", "HR_Manager"}

# Roles that can manage access controls
ACCESS_CONTROL_ROLES = {"HR_Admin"}

# All employees can view their own data (GDPR Article 15)
# This is enforced separately in the endpoints


def get_role_level(role: str) -> int:
    """
    Get the hierarchy level for a role.

    Args:
        role: Role name

    Returns:
        Hierarchy level (higher = more privilege)
    """
    return ROLE_HIERARCHY.get(role, 0)


def is_higher_or_equal_role(actor_role: str, target_role: str) -> bool:
    """
    Check if actor role is higher than or equal to target role.

    Args:
        actor_role: Role of the user performing the action
        target_role: Role of the target user

    Returns:
        True if actor has same or higher privilege
    """
    return get_role_level(actor_role) >= get_role_level(target_role)


def can_access_full_compliance_data(role: str) -> bool:
    """
    Check if role can access full compliance data.

    Only HR_Admin has full access to all compliance operations.

    Args:
        role: User role

    Returns:
        True if role has full compliance access
    """
    return role in COMPLIANCE_ADMIN_ROLES


def can_view_data_inventory(role: str) -> bool:
    """
    Check if role can view data inventory.

    HR_Admin and HR_Manager can view data inventory.

    Args:
        role: User role

    Returns:
        True if role can view data inventory
    """
    return role in DATA_INVENTORY_ROLES


def can_view_retention_reports(role: str) -> bool:
    """
    Check if role can view retention reports.

    HR_Admin and HR_Manager can view retention reports.

    Args:
        role: User role

    Returns:
        True if role can view retention reports
    """
    return role in RETENTION_REPORT_ROLES


def can_manage_access_controls(role: str) -> bool:
    """
    Check if role can manage access controls.

    Only HR_Admin can manage data access controls.

    Args:
        role: User role

    Returns:
        True if role can manage access controls
    """
    return role in ACCESS_CONTROL_ROLES


def can_view_employee_data_about_me(
    actor_id: str,
    actor_role: str,
    target_employee_id: str,
) -> bool:
    """
    Check if actor can view data-about-me for target employee.

    Per GDPR Article 15, employees can always view their own data.
    HR_Admin can view any employee's data.
    HR_Manager can view data for employees below them.
    Managers can view limited data for their team members.

    Args:
        actor_id: ID of the user making the request
        actor_role: Role of the user making the request
        target_employee_id: ID of the employee whose data is requested

    Returns:
        True if actor can view the data
    """
    # Employees can always view their own data (GDPR right)
    if actor_id == target_employee_id:
        return True

    # HR_Admin can view any employee's data
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can view data for employees (but not other HR roles)
    if actor_role == "HR_Manager":
        # In a full implementation, this would check the target's role
        # For now, HR_Manager can view non-admin data
        return True

    # Managers have limited access (typically their team only)
    # In a full implementation, this would check team membership
    if actor_role == "manager":
        return False  # Require explicit team membership check

    return False


def can_request_data_deletion(
    actor_id: str,
    actor_role: str,
    target_employee_id: str,
) -> bool:
    """
    Check if actor can request data deletion for target employee.

    Per GDPR Article 17 (Right to Erasure):
    - Employees can request deletion of their own data
    - HR_Admin can process deletion requests

    Note: Some data may be exempt from deletion due to legal requirements.

    Args:
        actor_id: ID of the user making the request
        actor_role: Role of the user making the request
        target_employee_id: ID of the employee whose data deletion is requested

    Returns:
        True if actor can request data deletion
    """
    # Employees can request deletion of their own data
    if actor_id == target_employee_id:
        return True

    # HR_Admin can process any deletion request
    if actor_role == "HR_Admin":
        return True

    return False


def can_export_employee_data(
    actor_id: str,
    actor_role: str,
    target_employee_id: str,
) -> bool:
    """
    Check if actor can export data for target employee.

    Per GDPR Article 20 (Right to Data Portability):
    - Employees can export their own data
    - HR_Admin can export any employee's data

    Args:
        actor_id: ID of the user making the request
        actor_role: Role of the user making the request
        target_employee_id: ID of the employee whose data is to be exported

    Returns:
        True if actor can export the data
    """
    # Employees can export their own data
    if actor_id == target_employee_id:
        return True

    # HR_Admin can export any data
    if actor_role == "HR_Admin":
        return True

    return False


def filter_data_inventory_for_role(
    inventory_items: list[dict[str, Any]],
    role: str,
) -> list[dict[str, Any]]:
    """
    Filter data inventory items based on role.

    HR_Admin sees everything.
    HR_Manager sees non-admin related data.
    Others see limited information.

    Args:
        inventory_items: List of data inventory items
        role: User role

    Returns:
        Filtered list of inventory items
    """
    if role == "HR_Admin":
        return inventory_items

    if role == "HR_Manager":
        # HR_Manager can see most data but may have some restrictions
        return [
            item
            for item in inventory_items
            if item.get("access_control_level") != "confidential"
            or item.get("data_type") != "admin"
        ]

    # Other roles see very limited data
    return [
        item
        for item in inventory_items
        if item.get("access_control_level") in ("public", "internal")
    ]


def filter_retention_report_for_role(
    retention_items: list[dict[str, Any]],
    actor_id: str,
    role: str,
) -> list[dict[str, Any]]:
    """
    Filter retention report items based on role.

    HR_Admin sees all retention records.
    HR_Manager sees non-admin retention records.
    Others only see their own data's retention status.

    Args:
        retention_items: List of retention report items
        actor_id: ID of the requesting user
        role: User role

    Returns:
        Filtered list of retention items
    """
    if role == "HR_Admin":
        return retention_items

    if role == "HR_Manager":
        # HR_Manager sees retention for non-admin users
        return [
            item
            for item in retention_items
            if item.get("data_subject_role") not in ("HR_Admin", "HR_Manager")
        ]

    # Others only see their own retention records
    return [item for item in retention_items if item.get("data_subject") == actor_id]


def get_accessible_data_types_for_role(role: str) -> list[str]:
    """
    Get list of data types accessible to a role.

    Args:
        role: User role

    Returns:
        List of accessible data type names
    """
    if role == "HR_Admin":
        return [
            "personal",
            "sensitive",
            "employment",
            "financial",
            "health",
            "operational",
            "admin",
        ]

    if role == "HR_Manager":
        return ["personal", "employment", "operational"]

    if role == "manager":
        return ["employment", "operational"]

    # Employee
    return ["personal", "employment"]


def get_gdpr_rights_for_role(role: str) -> dict[str, bool]:
    """
    Get GDPR rights available for a role.

    All employees have basic GDPR rights over their own data.
    HR roles have additional rights to process requests.

    Args:
        role: User role

    Returns:
        Dictionary of GDPR rights and whether they're available
    """
    # Base rights for all employees (over their own data)
    rights = {
        "article_15_right_of_access": True,  # View own data
        "article_16_right_to_rectification": True,  # Request corrections
        "article_17_right_to_erasure": True,  # Request deletion
        "article_18_right_to_restriction": True,  # Restrict processing
        "article_20_right_to_portability": True,  # Export data
        "article_21_right_to_object": True,  # Object to processing
    }

    # Admin rights for processing requests
    if role in COMPLIANCE_ADMIN_ROLES:
        rights.update(
            {
                "process_access_requests": True,
                "process_deletion_requests": True,
                "process_export_requests": True,
                "view_data_inventory": True,
                "view_retention_reports": True,
                "manage_access_controls": True,
            }
        )
    elif role == "HR_Manager":
        rights.update(
            {
                "process_access_requests": False,
                "process_deletion_requests": False,
                "process_export_requests": False,
                "view_data_inventory": True,
                "view_retention_reports": True,
                "manage_access_controls": False,
            }
        )
    else:
        rights.update(
            {
                "process_access_requests": False,
                "process_deletion_requests": False,
                "process_export_requests": False,
                "view_data_inventory": False,
                "view_retention_reports": False,
                "manage_access_controls": False,
            }
        )

    return rights


def log_compliance_access(
    actor_id: str,
    actor_role: str,
    action: str,
    target: str,
    allowed: bool,
    reason: Optional[str] = None,
) -> None:
    """
    Log compliance access attempts for audit purposes.

    Args:
        actor_id: ID of the user attempting access
        actor_role: Role of the user
        action: Action being attempted
        target: Target of the action
        allowed: Whether access was allowed
        reason: Optional reason for decision
    """
    status = "ALLOWED" if allowed else "DENIED"
    log_message = (
        f"Compliance access {status}: "
        f"actor={actor_id}, role={actor_role}, "
        f"action={action}, target={target}"
    )

    if reason:
        log_message += f", reason={reason}"

    if allowed:
        logger.info(log_message)
    else:
        logger.warning(log_message)
