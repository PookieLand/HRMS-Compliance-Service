"""
Redis Cache Service for Compliance Service.

Provides caching for:
- Data inventory queries
- Employee data access queries
- Retention report caching
- Metrics and counters
- Event deduplication
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

import redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ComplianceCacheService:
    """
    Redis cache service for Compliance Service.
    Handles caching of compliance queries and metrics.
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Connect to Redis server.

        Returns:
            True if connection successful
        """
        if self._client is not None and self._connected:
            return True

        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info(
                f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}"
            )
            return True
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            try:
                self._client.close()
                self._connected = False
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._connected or self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def _ensure_connected(self) -> bool:
        """Ensure Redis connection is active."""
        if not self.is_connected():
            return self.connect()
        return True

    # ==========================================
    # Data Inventory Cache
    # ==========================================

    def get_data_inventory(
        self,
        category_id: Optional[int] = None,
        data_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Optional[dict[str, Any]]:
        """
        Get cached data inventory query result.

        Args:
            category_id: Optional category filter
            data_type: Optional data type filter
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Cached result or None
        """
        if not self._ensure_connected():
            return None

        cache_key = f"compliance:inventory:{category_id}:{data_type}:{skip}:{limit}"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading inventory cache: {e}")
        return None

    def set_data_inventory(
        self,
        result: dict[str, Any],
        category_id: Optional[int] = None,
        data_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache data inventory query result.

        Args:
            result: Query result to cache
            category_id: Category filter used
            data_type: Data type filter used
            skip: Pagination offset
            limit: Pagination limit
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:inventory:{category_id}:{data_type}:{skip}:{limit}"
        ttl = ttl_seconds or settings.CACHE_TTL_INVENTORY
        try:
            self._client.setex(cache_key, ttl, json.dumps(result, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting inventory cache: {e}")
            return False

    def invalidate_inventory_cache(self) -> int:
        """
        Invalidate all inventory cache entries.

        Returns:
            Number of keys deleted
        """
        if not self._ensure_connected():
            return 0

        try:
            keys = self._client.keys("compliance:inventory:*")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error invalidating inventory cache: {e}")
            return 0

    # ==========================================
    # Employee Data About Me Cache
    # ==========================================

    def get_employee_data_summary(self, employee_id: str) -> Optional[dict[str, Any]]:
        """
        Get cached employee data summary (data-about-me).

        Args:
            employee_id: Employee ID

        Returns:
            Cached result or None
        """
        if not self._ensure_connected():
            return None

        cache_key = f"compliance:employee_data:{employee_id}"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading employee data cache: {e}")
        return None

    def set_employee_data_summary(
        self,
        employee_id: str,
        result: dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache employee data summary.

        Args:
            employee_id: Employee ID
            result: Data summary to cache
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:employee_data:{employee_id}"
        ttl = ttl_seconds or settings.CACHE_TTL_EMPLOYEE_DATA
        try:
            self._client.setex(cache_key, ttl, json.dumps(result, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting employee data cache: {e}")
            return False

    def invalidate_employee_data_cache(self, employee_id: str) -> bool:
        """
        Invalidate employee data cache.

        Args:
            employee_id: Employee ID

        Returns:
            True if deleted successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:employee_data:{employee_id}"
        try:
            self._client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error invalidating employee data cache: {e}")
            return False

    # ==========================================
    # Retention Report Cache
    # ==========================================

    def get_retention_report(
        self,
        status: Optional[str] = None,
        days_threshold: int = 30,
    ) -> Optional[dict[str, Any]]:
        """
        Get cached retention report.

        Args:
            status: Optional status filter
            days_threshold: Days threshold for expiring_soon

        Returns:
            Cached result or None
        """
        if not self._ensure_connected():
            return None

        cache_key = f"compliance:retention:{status}:{days_threshold}"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading retention cache: {e}")
        return None

    def set_retention_report(
        self,
        result: dict[str, Any],
        status: Optional[str] = None,
        days_threshold: int = 30,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache retention report.

        Args:
            result: Report to cache
            status: Status filter used
            days_threshold: Days threshold used
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:retention:{status}:{days_threshold}"
        ttl = ttl_seconds or settings.CACHE_TTL_RETENTION
        try:
            self._client.setex(cache_key, ttl, json.dumps(result, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting retention cache: {e}")
            return False

    def invalidate_retention_cache(self) -> int:
        """
        Invalidate all retention report cache entries.

        Returns:
            Number of keys deleted
        """
        if not self._ensure_connected():
            return 0

        try:
            keys = self._client.keys("compliance:retention:*")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error invalidating retention cache: {e}")
            return 0

    # ==========================================
    # Metrics and Counters
    # ==========================================

    def get_compliance_metrics(
        self, date: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Get cached compliance metrics for dashboard.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Cached metrics or None
        """
        if not self._ensure_connected():
            return None

        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        cache_key = f"compliance:metrics:{date}"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading metrics cache: {e}")
        return None

    def set_compliance_metrics(
        self,
        metrics: dict[str, Any],
        date: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache compliance metrics.

        Args:
            metrics: Metrics to cache
            date: Date string (YYYY-MM-DD)
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        cache_key = f"compliance:metrics:{date}"
        ttl = ttl_seconds or settings.CACHE_TTL_METRICS
        try:
            self._client.setex(cache_key, ttl, json.dumps(metrics, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting metrics cache: {e}")
            return False

    def increment_counter(self, counter_name: str, amount: int = 1) -> int:
        """
        Increment a counter.

        Args:
            counter_name: Name of the counter
            amount: Amount to increment

        Returns:
            New counter value
        """
        if not self._ensure_connected():
            return 0

        cache_key = f"compliance:counter:{counter_name}"
        try:
            value = self._client.incrby(cache_key, amount)
            # Set expiry for daily counters
            if ":" in counter_name and counter_name.split(":")[-1].startswith("20"):
                self._client.expire(cache_key, 86400 * 7)  # Keep for 7 days
            return value
        except Exception as e:
            logger.error(f"Error incrementing counter: {e}")
            return 0

    def get_counter(self, counter_name: str) -> int:
        """
        Get counter value.

        Args:
            counter_name: Name of the counter

        Returns:
            Counter value or 0
        """
        if not self._ensure_connected():
            return 0

        cache_key = f"compliance:counter:{counter_name}"
        try:
            value = self._client.get(cache_key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Error reading counter: {e}")
            return 0

    # ==========================================
    # Event Deduplication
    # ==========================================

    def is_duplicate_event(self, event_id: str) -> bool:
        """
        Check if an event has already been processed.

        Args:
            event_id: Unique event identifier

        Returns:
            True if event was already processed
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:event_processed:{event_id}"
        try:
            return self._client.exists(cache_key) > 0
        except Exception as e:
            logger.error(f"Error checking duplicate event: {e}")
            return False

    def mark_event_processed(
        self,
        event_id: str,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Mark an event as processed.

        Args:
            event_id: Unique event identifier
            ttl_seconds: TTL for deduplication entry

        Returns:
            True if marked successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:event_processed:{event_id}"
        ttl = ttl_seconds or settings.CACHE_TTL_DEDUP
        try:
            self._client.setex(cache_key, ttl, "1")
            return True
        except Exception as e:
            logger.error(f"Error marking event processed: {e}")
            return False

    # ==========================================
    # Access Control Cache
    # ==========================================

    def get_employee_access_controls(
        self, employee_id: str
    ) -> Optional[list[dict[str, Any]]]:
        """
        Get cached access controls for an employee.

        Args:
            employee_id: Employee ID

        Returns:
            Cached access controls or None
        """
        if not self._ensure_connected():
            return None

        cache_key = f"compliance:access_controls:{employee_id}"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading access controls cache: {e}")
        return None

    def set_employee_access_controls(
        self,
        employee_id: str,
        access_controls: list[dict[str, Any]],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache employee access controls.

        Args:
            employee_id: Employee ID
            access_controls: Access control list
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = f"compliance:access_controls:{employee_id}"
        ttl = ttl_seconds or settings.CACHE_TTL_ACCESS_CONTROLS
        try:
            self._client.setex(cache_key, ttl, json.dumps(access_controls, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting access controls cache: {e}")
            return False

    def invalidate_access_controls_cache(
        self, employee_id: Optional[str] = None
    ) -> int:
        """
        Invalidate access controls cache.

        Args:
            employee_id: Optional employee ID (if None, invalidate all)

        Returns:
            Number of keys deleted
        """
        if not self._ensure_connected():
            return 0

        try:
            if employee_id:
                cache_key = f"compliance:access_controls:{employee_id}"
                return self._client.delete(cache_key)
            else:
                keys = self._client.keys("compliance:access_controls:*")
                if keys:
                    return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error invalidating access controls cache: {e}")
            return 0

    # ==========================================
    # Data Category Cache
    # ==========================================

    def get_data_categories(self) -> Optional[list[dict[str, Any]]]:
        """
        Get cached data categories.

        Returns:
            Cached categories or None
        """
        if not self._ensure_connected():
            return None

        cache_key = "compliance:categories"
        try:
            data = self._client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading categories cache: {e}")
        return None

    def set_data_categories(
        self,
        categories: list[dict[str, Any]],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Cache data categories.

        Args:
            categories: Categories to cache
            ttl_seconds: Cache TTL in seconds

        Returns:
            True if cached successfully
        """
        if not self._ensure_connected():
            return False

        cache_key = "compliance:categories"
        ttl = ttl_seconds or settings.CACHE_TTL_CATEGORIES
        try:
            self._client.setex(cache_key, ttl, json.dumps(categories, default=str))
            return True
        except Exception as e:
            logger.error(f"Error setting categories cache: {e}")
            return False

    def invalidate_categories_cache(self) -> bool:
        """
        Invalidate categories cache.

        Returns:
            True if deleted successfully
        """
        if not self._ensure_connected():
            return False

        try:
            self._client.delete("compliance:categories")
            return True
        except Exception as e:
            logger.error(f"Error invalidating categories cache: {e}")
            return False


# Global cache instance
_cache_service: Optional[ComplianceCacheService] = None


def init_cache() -> ComplianceCacheService:
    """Initialize and return the global cache service."""
    global _cache_service
    if _cache_service is None:
        _cache_service = ComplianceCacheService()
        _cache_service.connect()
    return _cache_service


def get_cache_service() -> ComplianceCacheService:
    """Get the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        return init_cache()
    return _cache_service


def close_cache() -> None:
    """Close the global cache connection."""
    global _cache_service
    if _cache_service is not None:
        _cache_service.disconnect()
        _cache_service = None
