"""
Thread-safe validation result cache service.

Caches external validation service results (Nominatim, Overpass, AI validation)
with TTL support and statistics tracking.
"""

import time
from threading import Lock, RLock
from typing import Any, Dict, Optional, Tuple
from utils.helpers import normalize_text, coerce_float
from utils.logger import logger


class CacheEntry:
    """Represents a cached value with timestamp for TTL checking."""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        return (time.time() - self.created_at) > self.ttl_seconds


class ValidationResultCache:
    """
    Thread-safe cache for validation results.
    
    Cache key format: (normalized_name, rounded_lat, rounded_lon)
    - normalized_name: lowercased, trimmed, special chars removed
    - rounded_lat: latitude rounded to 4 decimal places (~11 meters)
    - rounded_lon: longitude rounded to 4 decimal places (~11 meters)
    """
    
    def __init__(self, ttl_seconds: int = 86400):  # Default 24 hours
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds. Default 24 hours.
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple, CacheEntry] = {}
        self._lock = RLock()  # Reentrant lock for nested calls
        
        # Statistics
        self._stats_lock = Lock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "nominatim_hits": 0,
            "nominatim_misses": 0,
            "overpass_hits": 0,
            "overpass_misses": 0,
            "ai_validation_hits": 0,
            "ai_validation_misses": 0,
            "expired_entries_removed": 0,
        }
    
    @staticmethod
    def _build_key(record: Dict[str, Any], name_field: str = "name") -> Tuple[str, float, float]:
        """
        Build cache key from record.
        
        Args:
            record: Cemetery record dictionary
            name_field: Field name to extract the cemetery name
            
        Returns:
            Tuple of (normalized_name, rounded_lat, rounded_lon)
        """
        name = record.get(name_field, "")
        lat = coerce_float(record.get("latitude"))
        lon = coerce_float(record.get("longitude"))
        
        if lat is None or lon is None:
            return None
        
        # Normalize name: lowercase, trim, remove special chars
        normalized_name = normalize_text(name) if name else ""
        
        # Round coordinates to 4 decimals (approximately 11 meters precision)
        rounded_lat = round(lat, 4)
        rounded_lon = round(lon, 4)
        
        return (normalized_name, rounded_lat, rounded_lon)
    
    def get_nominatim(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached Nominatim result for a record.
        
        Args:
            record: Cemetery record
            
        Returns:
            Cached Nominatim result or None if not cached/expired
        """
        key = self._build_key(record)
        if key is None:
            return None
        
        cache_key = ("nominatim", *key)
        return self._get(cache_key, "nominatim")
    
    def set_nominatim(self, record: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Cache Nominatim result for a record.
        
        Args:
            record: Cemetery record
            result: Nominatim enrichment result
        """
        key = self._build_key(record)
        if key is None:
            return
        
        cache_key = ("nominatim", *key)
        self._set(cache_key, result)
    
    def get_overpass(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached Overpass result for a record.
        
        Args:
            record: Cemetery record
            
        Returns:
            Cached Overpass result or None if not cached/expired
        """
        key = self._build_key(record)
        if key is None:
            return None
        
        cache_key = ("overpass", *key)
        return self._get(cache_key, "overpass")
    
    def set_overpass(self, record: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Cache Overpass result for a record.
        
        Args:
            record: Cemetery record
            result: Overpass verification result
        """
        key = self._build_key(record)
        if key is None:
            return
        
        cache_key = ("overpass", *key)
        self._set(cache_key, result)
    
    def get_ai_validation(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached AI validation result for a record.
        
        Args:
            record: Cemetery record
            
        Returns:
            Cached AI validation result or None if not cached/expired
        """
        key = self._build_key(record)
        if key is None:
            return None
        
        cache_key = ("ai_validation", *key)
        return self._get(cache_key, "ai_validation")
    
    def set_ai_validation(self, record: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Cache AI validation result for a record.
        
        Args:
            record: Cemetery record
            result: AI validation result
        """
        key = self._build_key(record)
        if key is None:
            return
        
        cache_key = ("ai_validation", *key)
        self._set(cache_key, result)
    
    def _get(self, key: Tuple, service_name: str = "generic") -> Optional[Any]:
        """
        Internal get with statistics tracking.
        
        Args:
            key: Cache key
            service_name: Name of service for statistics
            
        Returns:
            Cached value or None
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired():
                    # Remove expired entry
                    del self._cache[key]
                    with self._stats_lock:
                        self.stats["expired_entries_removed"] += 1
                        self.stats["misses"] += 1
                        if service_name != "generic":
                            self.stats[f"{service_name}_misses"] += 1
                    return None
                
                # Cache hit
                with self._stats_lock:
                    self.stats["hits"] += 1
                    if service_name != "generic":
                        self.stats[f"{service_name}_hits"] += 1
                
                return entry.value
            else:
                # Cache miss
                with self._stats_lock:
                    self.stats["misses"] += 1
                    if service_name != "generic":
                        self.stats[f"{service_name}_misses"] += 1
                
                return None
    
    def _set(self, key: Tuple, value: Any) -> None:
        """
        Internal set.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = CacheEntry(value, self.ttl_seconds)
    
    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        with self._lock:
            self._cache.clear()
        
        with self._stats_lock:
            self.stats = {
                "hits": 0,
                "misses": 0,
                "nominatim_hits": 0,
                "nominatim_misses": 0,
                "overpass_hits": 0,
                "overpass_misses": 0,
                "ai_validation_hits": 0,
                "ai_validation_misses": 0,
                "expired_entries_removed": 0,
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics including hit rate
        """
        with self._stats_lock:
            stats = self.stats.copy()
        
        total_requests = stats["hits"] + stats["misses"]
        hit_rate = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0.0
        
        stats["total_requests"] = total_requests
        stats["hit_rate_percent"] = round(hit_rate, 2)
        
        return stats
    
    def log_stats(self, logger_func=None) -> None:
        """
        Log cache statistics.
        
        Args:
            logger_func: Optional logger function (defaults to logger.info)
        """
        if logger_func is None:
            logger_func = logger.info
        
        stats = self.get_stats()
        
        logger_func("=" * 60)
        logger_func("CACHE STATISTICS")
        logger_func("=" * 60)
        logger_func(f"Total Requests: {stats['total_requests']}")
        logger_func(f"Cache Hits: {stats['hits']}")
        logger_func(f"Cache Misses: {stats['misses']}")
        logger_func(f"Hit Rate: {stats['hit_rate_percent']}%")
        logger_func(f"Expired Entries Removed: {stats['expired_entries_removed']}")
        logger_func("-" * 60)
        logger_func("Service-Specific Statistics:")
        logger_func(f"  Nominatim - Hits: {stats['nominatim_hits']}, Misses: {stats['nominatim_misses']}")
        logger_func(f"  Overpass  - Hits: {stats['overpass_hits']}, Misses: {stats['overpass_misses']}")
        logger_func(f"  AI Validation - Hits: {stats['ai_validation_hits']}, Misses: {stats['ai_validation_misses']}")
        logger_func("=" * 60)


# Global cache instance
_global_cache: Optional[ValidationResultCache] = None
_cache_lock = Lock()


def get_cache(ttl_seconds: int = 86400) -> ValidationResultCache:
    """
    Get or create the global cache instance.
    
    Args:
        ttl_seconds: TTL for cache entries (only used on first call)
        
    Returns:
        Global ValidationResultCache instance
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = ValidationResultCache(ttl_seconds=ttl_seconds)
                logger.info(f"Initialized global cache with TTL: {ttl_seconds} seconds")
    
    return _global_cache


def reset_cache() -> None:
    """Reset the global cache (useful for testing)."""
    global _global_cache
    
    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
