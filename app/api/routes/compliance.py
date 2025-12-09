"""
Compliance API routes.
Handles GDPR compliance endpoints for data inventory, access control, and retention.
Implements:
- GET /compliance/data-inventory (GDPR Article 30 - Records of Processing Activities)
- GET /compliance/employee/{employee_id}/data-about-me (GDPR Article 15 - Right of Access)
- GET /compliance/employee/{employee_id}/access-controls (Access control visibility)
- GET /compliance/data-retention-report (GDPR Article 5 - Storage Limitation)
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.dependencies import SessionDep
from app.core.cache import get_cache_service
from app.core.logging import get_logger
from app.core.rbac import (
    can_view_data_inventory,
    can_view_employee_data_about_me,
    can_view_retention_reports,
    filter_data_inventory_for_role,
    filter_retention_report_for_role,
    log_compliance_access,
)
from app.core.security import TokenData, get_current_active_user
from app.models.data_inventory import DataCategory, DataInventory
from app.models.employee_data_access import DataRetention, EmployeeDataAccess

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/compliance",
    tags=["compliance"],
    responses={404: {"description": "Resource not found"}},
)


def _get_user_role(user: TokenData) -> str:
    """Extract the primary role from user token."""
    if "HR_Admin" in user.roles or "admin" in user.roles:
        return "HR_Admin"
    elif "HR_Manager" in user.roles:
        return "HR_Manager"
    elif "manager" in user.roles:
        return "manager"
    return "employee"


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
    **Required Role**: HR_Admin or HR_Manager

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
    user_role = _get_user_role(current_user)

    # Check RBAC permissions
    if not can_view_data_inventory(user_role):
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_data_inventory",
            target="all",
            allowed=False,
            reason="Insufficient permissions",
        )
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view the data inventory. Required role: HR_Admin or HR_Manager.",
        )

    logger.info(
        f"Data inventory request from user {current_user.sub} with filters: "
        f"category={category_id}, type={data_type}, sensitivity={sensitivity_level}"
    )

    # Try to get from cache first
    cache = get_cache_service()
    cached_result = cache.get_data_inventory(
        category_id=category_id,
        data_type=data_type,
        skip=skip,
        limit=limit,
    )

    if cached_result:
        logger.debug("Returning cached data inventory")
        # Apply role-based filtering to cached result
        if "inventory" in cached_result:
            cached_result["inventory"] = filter_data_inventory_for_role(
                cached_result["inventory"], user_role
            )
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_data_inventory",
            target="all",
            allowed=True,
        )
        return cached_result

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

    # Build inventory list
    inventory_list = [
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
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in inventory
    ]

    categories_list = [
        {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "sensitivity_level": cat.sensitivity_level,
        }
        for cat in categories
    ]

    # Build response
    result = {
        "count": len(inventory_list),
        "skip": skip,
        "limit": limit,
        "inventory": inventory_list,
        "categories": categories_list,
        "gdpr_article": "Article 30 - Records of Processing Activities",
        "report_generated_at": datetime.utcnow().isoformat(),
    }

    # Cache the result
    cache.set_data_inventory(
        result=result,
        category_id=category_id,
        data_type=data_type,
        skip=skip,
        limit=limit,
    )

    # Apply role-based filtering
    result["inventory"] = filter_data_inventory_for_role(result["inventory"], user_role)

    log_compliance_access(
        actor_id=current_user.sub,
        actor_role=user_role,
        action="view_data_inventory",
        target="all",
        allowed=True,
    )

    return result


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
    Note: Employees can only view their own data. HR_Admin can view any employee's data.

    Args:
        employee_id: The employee ID to get data about

    Returns:
    - Simple summary of employee's personal data
    - Retention and deletion schedule
    - Access information
    """
    user_role = _get_user_role(current_user)

    # Check RBAC permissions using our rbac module
    if not can_view_employee_data_about_me(
        actor_id=current_user.sub,
        actor_role=user_role,
        target_employee_id=employee_id,
    ):
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_data_about_me",
            target=employee_id,
            allowed=False,
            reason="Not authorized to view other employee data",
        )
        raise HTTPException(
            status_code=403,
            detail="You can only view your own data. Contact HR Admin for access to other employee data.",
        )

    logger.info(f"Fetching data-about-me for employee {employee_id}")

    # Try to get from cache first
    cache = get_cache_service()
    cached_result = cache.get_employee_data_summary(employee_id)

    if cached_result:
        logger.debug(f"Returning cached data summary for employee {employee_id}")
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_data_about_me",
            target=employee_id,
            allowed=True,
        )
        return cached_result

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
                    "deletion_date": (
                        record.retention_expires_at.isoformat()
                        if record.retention_expires_at
                        else None
                    ),
                    "storage_location": inventory.storage_location,
                    "purpose": inventory.purpose_of_processing,
                }

    # Find earliest deletion date
    deletion_dates = [
        r.retention_expires_at for r in retention_records if r.retention_expires_at
    ]
    next_deletion = min(deletion_dates).isoformat() if deletion_dates else None

    # Count active access grants
    access_count = len(
        session.exec(
            select(EmployeeDataAccess).where(EmployeeDataAccess.is_active.is_(True))
        ).all()
    )

    result = {
        "employee_id": employee_id,
        "data_summary": {
            "total_data_entries": len(retention_records),
            "data_categories": list(set(inv.data_type for inv in all_inventory)),
            "retention_policies": retention_summary,
            "next_scheduled_deletion": next_deletion,
        },
        "access_information": {
            "employees_with_access_to_your_data": access_count,
            "access_control_type": "Role-based access control (RBAC)",
        },
        "security_measures": {
            "encryption": "Applied to all sensitive data",
            "access_control": "Role-based access control enforced",
            "audit_logging": "All access logged and monitored",
        },
        "your_gdpr_rights": {
            "article_15_right_of_access": "This report",
            "article_16_right_to_rectification": "Contact HR to correct your data",
            "article_17_right_to_erasure": "Request deletion via HR",
            "article_20_data_portability": "Request data export via HR",
        },
        "gdpr_article": "Article 15 - Right of Access",
        "report_generated_at": datetime.utcnow().isoformat(),
    }

    # Cache the result
    cache.set_employee_data_summary(employee_id, result)

    log_compliance_access(
        actor_id=current_user.sub,
        actor_role=user_role,
        action="view_data_about_me",
        target=employee_id,
        allowed=True,
    )

    return result


# ========== Employee Access Controls Endpoint ==========


@router.get("/employee/{employee_id}/access-controls", response_model=dict)
async def get_employee_access_controls(
    employee_id: str,
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
) -> dict:
    """
    Get access controls for an employee - what data they can access.

    **Authentication Required**: Bearer token
    Note: Employees can view their own access controls. HR_Admin can view any.

    Args:
        employee_id: The employee ID to get access controls for

    Returns:
    - List of data categories the employee can access
    - Access levels and reasons
    """
    user_role = _get_user_role(current_user)

    # Check permissions
    if current_user.sub != employee_id and user_role not in ("HR_Admin", "HR_Manager"):
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_access_controls",
            target=employee_id,
            allowed=False,
        )
        raise HTTPException(
            status_code=403,
            detail="You can only view your own access controls.",
        )

    logger.info(f"Fetching access controls for employee {employee_id}")

    # Try cache first
    cache = get_cache_service()
    cached_result = cache.get_employee_access_controls(employee_id)

    if cached_result:
        logger.debug(f"Returning cached access controls for employee {employee_id}")
        return {"employee_id": employee_id, "access_controls": cached_result}

    # Query access controls
    access_query = select(EmployeeDataAccess).where(
        EmployeeDataAccess.employee_id == employee_id,
        EmployeeDataAccess.is_active.is_(True),
    )
    access_records = session.exec(access_query).all()

    access_list = []
    for record in access_records:
        inventory = session.get(DataInventory, record.data_inventory_id)
        access_list.append(
            {
                "id": record.id,
                "data_inventory_id": record.data_inventory_id,
                "data_name": inventory.data_name if inventory else "Unknown",
                "data_type": inventory.data_type if inventory else "Unknown",
                "access_level": record.access_level,
                "access_reason": record.access_reason,
                "role_based": record.role_based,
                "role_name": record.role_name,
                "granted_by": record.granted_by,
                "granted_at": (
                    record.granted_at.isoformat() if record.granted_at else None
                ),
                "expires_at": (
                    record.expires_at.isoformat() if record.expires_at else None
                ),
            }
        )

    # Cache the result
    cache.set_employee_access_controls(employee_id, access_list)

    log_compliance_access(
        actor_id=current_user.sub,
        actor_role=user_role,
        action="view_access_controls",
        target=employee_id,
        allowed=True,
    )

    return {
        "employee_id": employee_id,
        "total_access_entries": len(access_list),
        "role_based_accesses": sum(1 for a in access_list if a["role_based"]),
        "direct_accesses": sum(1 for a in access_list if not a["role_based"]),
        "access_controls": access_list,
        "report_generated_at": datetime.utcnow().isoformat(),
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

    **Authentication Required**: Bearer token
    **Required Role**: HR_Admin or HR_Manager

    Query Parameters:
    - status: Filter by retention status (active, expiring_soon, expired, deleted)
    - days_threshold: Days until expiration to mark as 'expiring_soon' (default: 30)

    Returns:
    - Comprehensive retention report
    - Data age analysis
    - Action items for compliance officers
    """
    user_role = _get_user_role(current_user)

    # Check RBAC permissions
    if not can_view_retention_reports(user_role):
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_retention_report",
            target="all",
            allowed=False,
            reason="Insufficient permissions",
        )
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view retention reports. Required role: HR_Admin or HR_Manager.",
        )

    logger.info(
        f"Data retention report requested by user {current_user.sub} with status filter: {status}"
    )

    # Try to get from cache first
    cache = get_cache_service()
    cached_result = cache.get_retention_report(
        status=status,
        days_threshold=days_threshold,
    )

    if cached_result:
        logger.debug("Returning cached retention report")
        # Apply role-based filtering
        if "retention_items" in cached_result:
            cached_result["retention_items"] = filter_retention_report_for_role(
                cached_result["retention_items"],
                actor_id=current_user.sub,
                role=user_role,
            )
        log_compliance_access(
            actor_id=current_user.sub,
            actor_role=user_role,
            action="view_retention_report",
            target="all",
            allowed=True,
        )
        return cached_result

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
        days_until_deletion = (record.retention_expires_at - now).days

        item = {
            "id": record.id,
            "data_name": inventory.data_name,
            "record_id": record.record_id,
            "data_created_at": record.data_created_at.isoformat(),
            "retention_expires_at": record.retention_expires_at.isoformat(),
            "days_until_deletion": days_until_deletion,
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
    for item in active_records + expiring_soon + expired_records + deleted_records:
        cat = item["category"]
        if cat not in summary_by_category:
            summary_by_category[cat] = {
                "total": 0,
                "active": 0,
                "expiring_soon": 0,
                "expired": 0,
                "deleted": 0,
            }
        summary_by_category[cat]["total"] += 1
        if item in active_records:
            summary_by_category[cat]["active"] += 1
        elif item in expiring_soon:
            summary_by_category[cat]["expiring_soon"] += 1
        elif item in expired_records:
            summary_by_category[cat]["expired"] += 1
        elif item in deleted_records:
            summary_by_category[cat]["deleted"] += 1

    result = {
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
            "urgent_action_required": len(expired_records) > 0,
        },
        "retention_items": all_items,
        "summary_by_category": summary_by_category,
        "gdpr_article": "Article 5 - Storage Limitation",
        "report_generated_at": datetime.utcnow().isoformat(),
        "threshold_days": days_threshold,
    }

    # Cache the result
    cache.set_retention_report(
        result=result,
        status=status,
        days_threshold=days_threshold,
    )

    # Apply role-based filtering
    result["retention_items"] = filter_retention_report_for_role(
        result["retention_items"],
        actor_id=current_user.sub,
        role=user_role,
    )

    log_compliance_access(
        actor_id=current_user.sub,
        actor_role=user_role,
        action="view_retention_report",
        target="all",
        allowed=True,
    )

    return result


# ========== Data Categories Endpoint ==========


@router.get("/data-categories", response_model=dict)
async def get_data_categories(
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(get_current_active_user)],
) -> dict:
    """
    Get all data categories defined in the system.

    **Authentication Required**: Bearer token
    **Required Role**: HR_Admin or HR_Manager

    Returns:
    - List of data categories with sensitivity levels
    """
    user_role = _get_user_role(current_user)

    if not can_view_data_inventory(user_role):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view data categories.",
        )

    # Try cache first
    cache = get_cache_service()
    cached_categories = cache.get_data_categories()

    if cached_categories:
        return {
            "categories": cached_categories,
            "count": len(cached_categories),
        }

    # Query categories
    categories = session.exec(select(DataCategory)).all()

    categories_list = [
        {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "sensitivity_level": cat.sensitivity_level,
            "created_at": cat.created_at.isoformat() if cat.created_at else None,
        }
        for cat in categories
    ]

    # Cache the result
    cache.set_data_categories(categories_list)

    return {
        "categories": categories_list,
        "count": len(categories_list),
        "report_generated_at": datetime.utcnow().isoformat(),
    }
