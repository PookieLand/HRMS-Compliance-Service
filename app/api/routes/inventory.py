"""
Data Inventory Management routes.
Handles CRUD operations for data inventory entries.
Implements GDPR Article 30 - Records of Processing Activities.
"""

from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlmodel import select, Session

from app.api.deps import SessionDep
from app.core.security import get_current_active_user, TokenData, require_role
from app.core.logging import get_logger
from app.models.data_inventory import DataInventory, DataCategory
from app.schemas.employee import (
    DataInventoryCreate,
    DataInventoryPublic,
    DataInventoryUpdate,
    DataCategoryCreate,
    DataCategoryPublic,
)

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/compliance/inventory",
    tags=["data-inventory-management"],
    responses={404: {"description": "Resource not found"}},
)


# ========== Data Category Management ==========


@router.post(
    "/categories",
    response_model=DataCategoryPublic,
    status_code=201,
    summary="Create data category",
)
async def create_category(
    category: DataCategoryCreate,
    session: SessionDep,
    current_user: Annotated[
        TokenData, Depends(require_role("admin", "compliance_officer"))
    ],
) -> DataCategory:
    """
    Create a new data category.

    Requires: admin or compliance_officer role

    Args:
        category: Category data
        session: Database session
        current_user: Current authenticated user

    Returns:
        Created category with ID
    """
    logger.info(f"Creating data category: {category.name} by user {current_user.sub}")

    # Check for duplicate
    existing = session.exec(
        select(DataCategory).where(DataCategory.name == category.name)
    ).first()
    if existing:
        logger.warning(f"Category {category.name} already exists")
        raise HTTPException(
            status_code=400, detail="Data category with this name already exists"
        )

    db_category = DataCategory.model_validate(category)
    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    logger.info(f"Data category created with ID: {db_category.id}")
    return db_category


@router.get(
    "/categories",
    response_model=list[DataCategoryPublic],
    summary="List all data categories",
)
async def list_categories(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[DataCategory]:
    """
    List all data categories with pagination.

    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 100, max: 100)

    Returns:
        List of data categories
    """
    logger.info(f"Listing data categories with skip={skip}, limit={limit}")
    categories = session.exec(select(DataCategory).offset(skip).limit(limit)).all()
    return list(categories)


@router.get(
    "/categories/{category_id}",
    response_model=DataCategoryPublic,
    summary="Get category details",
)
async def get_category(
    category_id: int,
    session: SessionDep,
) -> DataCategory:
    """
    Get details of a specific data category.

    Args:
        category_id: Category ID
        session: Database session

    Returns:
        Category details

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Fetching category: {category_id}")
    category = session.get(DataCategory, category_id)
    if not category:
        logger.warning(f"Category {category_id} not found")
        raise HTTPException(status_code=404, detail="Data category not found")
    return category


@router.patch(
    "/categories/{category_id}",
    response_model=DataCategoryPublic,
    summary="Update category",
)
async def update_category(
    category_id: int,
    category_update: DataCategoryCreate,
    session: SessionDep,
    current_user: Annotated[
        TokenData, Depends(require_role("admin", "compliance_officer"))
    ],
) -> DataCategory:
    """
    Update a data category.

    Requires: admin or compliance_officer role

    Args:
        category_id: Category ID to update
        category_update: New category data
        session: Database session
        current_user: Current authenticated user

    Returns:
        Updated category

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Updating category {category_id} by user {current_user.sub}")
    db_category = session.get(DataCategory, category_id)
    if not db_category:
        logger.warning(f"Category {category_id} not found for update")
        raise HTTPException(status_code=404, detail="Data category not found")

    update_data = category_update.model_dump(exclude_unset=True)
    db_category = db_category.sqlmodel_update(update_data)
    db_category.updated_at = datetime.utcnow()
    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    logger.info(f"Category {category_id} updated successfully")
    return db_category


@router.delete(
    "/categories/{category_id}",
    summary="Delete category",
)
async def delete_category(
    category_id: int,
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(require_role("admin"))],
) -> dict:
    """
    Delete a data category.

    Requires: admin role only

    Args:
        category_id: Category ID to delete
        session: Database session
        current_user: Current authenticated user

    Returns:
        Success confirmation

    Raises:
        HTTPException: 404 if not found, 400 if category has inventory items
    """
    logger.info(f"Deleting category {category_id} by user {current_user.sub}")
    db_category = session.get(DataCategory, category_id)
    if not db_category:
        logger.warning(f"Category {category_id} not found for deletion")
        raise HTTPException(status_code=404, detail="Data category not found")

    # Check if category has inventory items
    inventory_count = session.exec(
        select(DataInventory).where(DataInventory.category_id == category_id)
    ).all()
    if inventory_count:
        logger.warning(
            f"Cannot delete category {category_id}: has {len(inventory_count)} inventory items"
        )
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with existing inventory entries",
        )

    session.delete(db_category)
    session.commit()
    logger.info(f"Category {category_id} deleted successfully")
    return {"ok": True, "message": "Data category deleted"}


# ========== Data Inventory CRUD Operations ==========


@router.post(
    "/entries",
    response_model=DataInventoryPublic,
    status_code=201,
    summary="Create data inventory entry",
)
async def create_inventory_entry(
    inventory: DataInventoryCreate,
    session: SessionDep,
    current_user: Annotated[
        TokenData, Depends(require_role("admin", "compliance_officer"))
    ],
) -> DataInventory:
    """
    Create a new data inventory entry (GDPR Article 30 - RoPA).

    Requires: admin or compliance_officer role

    Args:
        inventory: Inventory entry data
        session: Database session
        current_user: Current authenticated user

    Returns:
        Created inventory entry with ID
    """
    logger.info(
        f"Creating data inventory entry: {inventory.data_name} by user {current_user.sub}"
    )

    # Verify category exists
    category = session.get(DataCategory, inventory.category_id)
    if not category:
        logger.warning(f"Category {inventory.category_id} not found")
        raise HTTPException(status_code=404, detail="Data category not found")

    db_inventory = DataInventory.model_validate(inventory)
    session.add(db_inventory)
    session.commit()
    session.refresh(db_inventory)
    logger.info(f"Data inventory entry created with ID: {db_inventory.id}")
    return db_inventory


@router.get(
    "/entries",
    response_model=list[DataInventoryPublic],
    summary="List all data inventory entries",
)
async def list_inventory_entries(
    session: SessionDep,
    category_id: int | None = Query(None),
    data_type: str | None = Query(None),
    access_level: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[DataInventory]:
    """
    List all data inventory entries with optional filtering.

    Query Parameters:
    - category_id: Filter by category ID
    - data_type: Filter by data type
    - access_level: Filter by access control level
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 100, max: 100)

    Returns:
        List of inventory entries
    """
    logger.info(
        f"Listing inventory entries with skip={skip}, limit={limit}, "
        f"category={category_id}, type={data_type}, access_level={access_level}"
    )

    query = select(DataInventory)

    if category_id is not None:
        query = query.where(DataInventory.category_id == category_id)
    if data_type is not None:
        query = query.where(DataInventory.data_type == data_type)
    if access_level is not None:
        query = query.where(DataInventory.access_control_level == access_level)

    entries = session.exec(query.offset(skip).limit(limit)).all()
    logger.info(f"Retrieved {len(entries)} inventory entries")
    return list(entries)


@router.get(
    "/entries/{inventory_id}",
    response_model=DataInventoryPublic,
    summary="Get inventory entry details",
)
async def get_inventory_entry(
    inventory_id: int,
    session: SessionDep,
) -> DataInventory:
    """
    Get details of a specific inventory entry.

    Args:
        inventory_id: Inventory entry ID
        session: Database session

    Returns:
        Inventory entry details

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Fetching inventory entry: {inventory_id}")
    entry = session.get(DataInventory, inventory_id)
    if not entry:
        logger.warning(f"Inventory entry {inventory_id} not found")
        raise HTTPException(status_code=404, detail="Data inventory entry not found")
    return entry


@router.patch(
    "/entries/{inventory_id}",
    response_model=DataInventoryPublic,
    summary="Update inventory entry",
)
async def update_inventory_entry(
    inventory_id: int,
    inventory_update: DataInventoryUpdate,
    session: SessionDep,
    current_user: Annotated[
        TokenData, Depends(require_role("admin", "compliance_officer"))
    ],
) -> DataInventory:
    """
    Update a data inventory entry.

    Requires: admin or compliance_officer role

    Args:
        inventory_id: Inventory entry ID to update
        inventory_update: Updated entry data
        session: Database session
        current_user: Current authenticated user

    Returns:
        Updated inventory entry

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Updating inventory entry {inventory_id} by user {current_user.sub}")
    db_entry = session.get(DataInventory, inventory_id)
    if not db_entry:
        logger.warning(f"Inventory entry {inventory_id} not found for update")
        raise HTTPException(status_code=404, detail="Data inventory entry not found")

    # Verify category if being updated
    if inventory_update.category_id is not None:
        category = session.get(DataCategory, inventory_update.category_id)
        if not category:
            logger.warning(f"Category {inventory_update.category_id} not found")
            raise HTTPException(status_code=404, detail="Data category not found")

    update_data = inventory_update.model_dump(exclude_unset=True)
    db_entry = db_entry.sqlmodel_update(update_data)
    db_entry.updated_at = datetime.utcnow()
    session.add(db_entry)
    session.commit()
    session.refresh(db_entry)
    logger.info(f"Inventory entry {inventory_id} updated successfully")
    return db_entry


@router.delete(
    "/entries/{inventory_id}",
    summary="Delete inventory entry",
)
async def delete_inventory_entry(
    inventory_id: int,
    session: SessionDep,
    current_user: Annotated[TokenData, Depends(require_role("admin"))],
) -> dict:
    """
    Delete a data inventory entry.

    Requires: admin role only

    Args:
        inventory_id: Inventory entry ID to delete
        session: Database session
        current_user: Current authenticated user

    Returns:
        Success confirmation

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Deleting inventory entry {inventory_id} by user {current_user.sub}")
    db_entry = session.get(DataInventory, inventory_id)
    if not db_entry:
        logger.warning(f"Inventory entry {inventory_id} not found for deletion")
        raise HTTPException(status_code=404, detail="Data inventory entry not found")

    session.delete(db_entry)
    session.commit()
    logger.info(f"Inventory entry {inventory_id} deleted successfully")
    return {"ok": True, "message": "Data inventory entry deleted"}


@router.get(
    "/entries/{inventory_id}/stats",
    summary="Get inventory entry statistics",
)
async def get_inventory_stats(
    inventory_id: int,
    session: SessionDep,
) -> dict:
    """
    Get statistics and metadata for an inventory entry.

    Args:
        inventory_id: Inventory entry ID
        session: Database session

    Returns:
        Statistics and metadata

    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Getting stats for inventory entry: {inventory_id}")
    entry = session.get(DataInventory, inventory_id)
    if not entry:
        logger.warning(f"Inventory entry {inventory_id} not found")
        raise HTTPException(status_code=404, detail="Data inventory entry not found")

    # Get category info
    category = session.get(DataCategory, entry.category_id)

    return {
        "inventory_id": inventory_id,
        "data_name": entry.data_name,
        "category": {
            "id": category.id if category else None,
            "name": category.name if category else None,
            "sensitivity_level": category.sensitivity_level if category else None,
        },
        "retention_info": {
            "retention_days": entry.retention_days,
            "policy": entry.retention_policy,
        },
        "access_info": {
            "access_control_level": entry.access_control_level,
            "encryption_status": entry.encryption_status,
            "third_party_sharing": entry.third_party_sharing,
        },
        "processing_info": {
            "legal_basis": entry.legal_basis,
            "purpose": entry.purpose_of_processing,
            "system": entry.processing_system,
        },
        "metadata": {
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "last_retention_check": entry.last_retention_check,
        },
    }
