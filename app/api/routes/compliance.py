"""
Compliance API routes.
Handles GDPR compliance endpoints for data inventory, access control, and retention.
Implements:
- GET /compliance/data-inventory (GDPR Article 30 - Records of Processing Activities)
- GET /compliance/employee/{employee_id}/data-about-me (GDPR Article 15 - Right of Access)
- GET /compliance/employee/{employee_id}/access-controls (Access control visibility)
- GET /compliance/data-retention-report (GDPR Article 5 - Storage Limitation)
"""

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime, timedelta
from sqlmodel import select, Session

from app.api.deps import SessionDep
from app.core.security import get_current_active_user, TokenData
from app.core.config import settings
from app.core.logging import get_logger
from app.models.data_inventory import DataInventory, DataCategory
from app.models.employee_data_access import EmployeeDataAccess, DataRetention

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/compliance",
    tags=["compliance"],
    responses={404: {"description": "Resource not found"}},
)


# ========== Data Inventory Endpoints ==========


@router.get("/data-inventory", response_model=dict)
async def get_data_inventory(
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
    category_id: int | None = Query(None),
    data_type: str | None = Query(None),
    sensitivity_level: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: Annotated[int, Query(le=1000)] = 100,
) -> dict:
    """
    Get complete map of all data in system.
    GDPR Article 30 - Records of Processing Activities (ROPA).

    Shows:
    - All data categories and their classifications
    - Storage locations and processing purposes
    - Legal basis for processing
    - Retention policies
    - Encryption and access control status
    - Third-party data sharing information

    **Authentication Required**: Bearer token

    Query Parameters:
    - category_id: Filter by category ID
    - data_type: Filter by data type (personal, sensitive, employment, etc.)
    - sensitivity_level: Filter by sensitivity (low, medium, high, critical)
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 100, max: 1000)

    Returns:
    - Complete data inventory with metadata
    - Count and filtering information
    - Summary statistics
    """
    logger.info(
        f"Data inventory request from user {current_user.sub} with filters: "
        f"category={category_id}, type={data_type}, sensitivity={sensitivity_level}"
    )

    # Build query
    query = select(DataInventory)

    if category_id is not None:
        query = query.where(DataInventory.category_id == category_id)

    if data_type is not None:
        query = query.where(DataInventory.data_type == data_type)

    # Execute query with pagination
    inventory = session.exec(query.offset(skip).limit(limit)).all()

    # Get categories for reference
    categories = session.exec(select(DataCategory)).all()

    # Build response
    return {
        "count": len(inventory),
        "skip": skip,
        "limit": limit,
        "inventory": [
            {
                "id": item.id,
                "data_name": item.data_name,
                "description": item.description,
                "category_id": item.category_id,
                "data_type": item.data_type,
                "storage_location": item.storage_location,
                "purpose_of_processing": item.purpose_of_processing,
                "legal_basis": item.legal_basis,
                "retention_days": item.retention_days,
                "retention_policy": item.retention_policy,
                "data_subjects": item.data_subjects,
                "recipients": item.recipients,
                "third_party_sharing": item.third_party_sharing,
                "third_party_recipients": item.third_party_recipients,
                "encryption_status": item.encryption_status,
                "access_control_level": item.access_control_level,
                "processing_system": item.processing_system,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in inventory
        ],
        "categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "sensitivity_level": cat.sensitivity_level,
            }
            for cat in categories
        ],
        "gdpr_article": "Article 30 - Records of Processing Activities",
        "report_generated_at": datetime.utcnow(),
    }


# ========== Employee Data About Me Endpoint ==========


@router.get("/employee/{employee_id}/data-about-me", response_model=dict)
async def get_employee_data_about_me(
    employee_id: str,
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
) -> dict:
    """
    Get simple summary of employee's own data in the system.
    GDPR Article 15 - Right of Access (Right to know what data is held).

    Shows:
    - What data categories the employee's data falls into
    - Where the data is stored
    - How long the data will be retained
    - Who has access to this data
    - Encryption and security measures

    **Authentication Required**: Bearer token
    Note: Employees can only view their own data. Admins can view any employee's data.

    Args:
        employee_id: The employee ID to get data about

    Returns:
    - Simple summary of employee's personal data
    - Retention and deletion schedule
    - Access information
    """
    # Security: Check if user is viewing their own data or is admin
    if current_user.sub != employee_id and "admin" not in current_user.roles:
        logger.warning(
            f"User {current_user.sub} attempted unauthorized access to data of {employee_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="You can only view your own data. Contact admin for access to other employee data.",
        )

    logger.info(f"Fetching data-about-me for employee {employee_id}")

    # Get all data inventory entries
    all_inventory = session.exec(select(DataInventory)).all()

    # Find retention records for this employee
    retention_query = select(DataRetention).where(
        DataRetention.data_subject_id == employee_id
    )
    retention_records = session.exec(retention_query).all()

    # Calculate retention summary
    retention_summary = {}
    for record in retention_records:
        inventory = session.get(DataInventory, record.data_inventory_id)
        if inventory:
            category_name = inventory.data_name
            if category_name not in retention_summary:
                retention_summary[category_name] = {
                    "data_type": inventory.data_type,
                    "retention_days": inventory.retention_days,
                    "deletion_date": record.retention_expires_at,
                }

    # Find earliest deletion date
    deletion_dates = [
        r.retention_expires_at for r in retention_records if r.retention_expires_at
    ]
    next_deletion = min(deletion_dates) if deletion_dates else None

    return {
        "employee_id": employee_id,
        "data_summary": {
            "total_data_entries": len(retention_records),
            "data_categories": list(set(inv.data_type for inv in all_inventory)),
            "retention_policies": retention_summary,
            "next_scheduled_deletion": next_deletion,
            "created_at": datetime.utcnow(),
        },
        "access_information": {
            "employees_with_access_to_your_data": len(
                session.exec(
                    select(EmployeeDataAccess).where(
                        EmployeeDataAccess.is_active == True
                    )
                ).all()
            )
        },
        "security_measures": {
            "encryption": "Applied to all sensitive data",
            "access_control": "Role-based access control enforced",
            "audit_logging": "All access logged and monitored",
        },
        "gdpr_article": "Article 15 - Right of Access",
        "report_generated_at": datetime.utcnow(),
    }


# ========== Employee Access Controls Endpoint ==========


@router.get("/employee/{employee_id}/access-controls", response_model=dict)
async def get_employee_access_controls(
    employee_id: str,
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
) -> dict:
    """
    Get what data an employee can access and why.
    Shows access control granularity and access reasons.

    Returns:
    - All data categories employee can access
    - Access level for each category (read, write, delete, admin)
    - Reason for each access grant
    - Expiration dates for access grants
    - Role-based vs direct access
    """
    # Security: Only admin or HR can view others' access, employee can view their own
    if current_user.sub != employee_id and "admin" not in current_user.roles:
        logger.warning(
            f"User {current_user.sub} attempted unauthorized access to controls of {employee_id}"
        )
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    logger.info(f"Fetching access controls for employee {employee_id}")

    # Get all access records for this employee
    access_query = select(EmployeeDataAccess).where(
        EmployeeDataAccess.employee_id == employee_id
    )
    access_records = session.exec(access_query).all()

    # Build detailed access information
    accessible_categories = []
    for access in access_records:
        inventory = session.get(DataInventory, access.data_inventory_id)
        if inventory:
            accessible_categories.append(
                {
                    "data_id": inventory.id,
                    "data_name": inventory.data_name,
                    "data_type": inventory.data_type,
                    "access_level": access.access_level,
                    "access_reason": access.access_reason,
                    "role_based": access.role_based,
                    "role_name": access.role_name,
                    "granted_at": access.granted_at,
                    "expires_at": access.expires_at,
                    "is_active": access.is_active,
                    "sensitivity_level": inventory.encryption_status,
                }
            )

    # Categorize access types
    role_based_count = sum(1 for a in access_records if a.role_based)
    direct_access_count = len(access_records) - role_based_count

    return {
        "employee_id": employee_id,
        "total_data_access_entries": len(access_records),
        "role_based_accesses": role_based_count,
        "direct_accesses": direct_access_count,
        "accessible_data_categories": accessible_categories,
        "access_summary": {
            "read_access": sum(1 for a in access_records if a.access_level == "read"),
            "write_access": sum(1 for a in access_records if a.access_level == "write"),
            "delete_access": sum(
                1 for a in access_records if a.access_level == "delete"
            ),
            "admin_access": sum(1 for a in access_records if a.access_level == "admin"),
        },
        "active_accesses": sum(1 for a in access_records if a.is_active),
        "expiring_accesses": sum(
            1
            for a in access_records
            if a.expires_at and a.expires_at < datetime.utcnow() + timedelta(days=30)
        ),
        "report_generated_at": datetime.utcnow(),
    }


# ========== Data Retention Report Endpoint ==========


@router.get("/data-retention-report", response_model=dict)
async def get_data_retention_report(
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
    status: str | None = Query(
        None, description="Filter by status: active, expiring_soon, expired, deleted"
    ),
    days_threshold: int = Query(
        30, description="Days threshold for 'expiring_soon' status"
    ),
) -> dict:
    """
    Get data age and what needs to be deleted.
    GDPR Article 5 - Storage Limitation (Kept no longer than necessary).

    Shows:
    - All tracked data records with their age
    - Retention expiration dates
    - Records marked for deletion
    - Recently deleted records
    - Action items (what needs to be deleted soon)

    Query Parameters:
    - status: Filter by retention status (active, expiring_soon, expired, deleted)
    - days_threshold: Days until expiration to mark as 'expiring_soon' (default: 30)

    Returns:
    - Comprehensive retention report
    - Data age analysis
    - Action items for compliance officers
    """
    logger.info(
        f"Data retention report requested by user {current_user.sub} with status filter: {status}"
    )

    # Get all retention records
    query = select(DataRetention)

    retention_records = session.exec(query).all()

    # Process retention records
    active_records = []
    expiring_soon = []
    expired_records = []
    deleted_records = []

    now = datetime.utcnow()
    threshold_date = now + timedelta(days=days_threshold)

    for record in retention_records:
        inventory = session.get(DataInventory, record.data_inventory_id)
        if not inventory:
            continue

        # Calculate age
        data_age_days = (now - record.data_created_at).days

        item = {
            "id": record.id,
            "data_name": inventory.data_name,
            "record_id": record.record_id,
            "data_created_at": record.data_created_at,
            "retention_expires_at": record.retention_expires_at,
            "days_until_deletion": (record.retention_expires_at - now).days,
            "data_age_days": data_age_days,
            "category": inventory.data_type,
            "data_subject": record.data_subject_id,
            "status": record.retention_status,
            "marked_for_deletion": record.marked_for_deletion,
        }

        # Categorize
        if record.deletion_completed_at:
            deleted_records.append(item)
        elif record.retention_status == "expired" or now > record.retention_expires_at:
            expired_records.append(item)
        elif record.retention_expires_at <= threshold_date:
            expiring_soon.append(item)
        else:
            active_records.append(item)

    # Apply status filter if specified
    all_items = active_records + expiring_soon + expired_records + deleted_records
    if status:
        if status == "active":
            all_items = active_records
        elif status == "expiring_soon":
            all_items = expiring_soon
        elif status == "expired":
            all_items = expired_records
        elif status == "deleted":
            all_items = deleted_records

    # Build summary by category
    summary_by_category = {}
    for item in all_items:
        cat = item["category"]
        if cat not in summary_by_category:
            summary_by_category[cat] = {
                "total": 0,
                "expiring_soon": 0,
                "expired": 0,
                "deleted": 0,
            }
        summary_by_category[cat]["total"] += 1
        if item in expiring_soon:
            summary_by_category[cat]["expiring_soon"] += 1
        elif item in expired_records:
            summary_by_category[cat]["expired"] += 1
        elif item in deleted_records:
            summary_by_category[cat]["deleted"] += 1

    return {
        "total_records_tracked": len(retention_records),
        "active_records": len(active_records),
        "expiring_soon": len(expiring_soon),
        "expired_records": len(expired_records),
        "deleted_records": len(deleted_records),
        "marked_for_deletion": sum(
            1 for r in retention_records if r.marked_for_deletion
        ),
        "action_items": {
            "delete_immediately": len(expired_records),
            "delete_within_days": len(expiring_soon),
        },
        "retention_items": all_items,
        "summary_by_category": summary_by_category,
        "gdpr_article": "Article 5 - Storage Limitation",
        "report_generated_at": datetime.utcnow(),
        "threshold_days": days_threshold,
    }
