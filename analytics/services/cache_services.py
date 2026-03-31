"""
Redis Caching Service for TeachLink
Optimizes frequently accessed data
"""
from django.core.cache import cache
from django.conf import settings
import json
import hashlib
from typing import Any, Optional

class CacheService:
    """
    Service for managing Redis cache
    """
    
    # Cache TTLs (in seconds)
    TTL = {
        'dashboard_teacher': 300,  # 5 minutes
        'dashboard_student': 60,    # 1 minute
        'risk_distribution': 600,   # 10 minutes
        'difficulty_ranking': 3600, # 1 hour
        'course_list': 300,         # 5 minutes
        'user_profile': 3600,       # 1 hour
        'quiz_statistics': 1800,    # 30 minutes
        'alert_counts': 60,         # 1 minute
    }
    
    @classmethod
    def get_key(cls, prefix: str, identifier: str) -> str:
        """Generate cache key"""
        return f"teachlink:{prefix}:{identifier}"
    
    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get value from cache"""
        return cache.get(key)
    
    @classmethod
    def set(cls, key: str, value: Any, ttl: str = 'default') -> bool:
        """Set value in cache with TTL"""
        ttl_seconds = cls.TTL.get(ttl, 300)
        return cache.set(key, value, ttl_seconds)
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete value from cache"""
        return cache.delete(key)
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """Delete all keys matching pattern"""
        from django.core.cache import caches
        cache_instance = caches['default']
        
        if hasattr(cache_instance, 'delete_pattern'):
            return cache_instance.delete_pattern(pattern)
        
        # Fallback for Redis
        keys = cache_instance.keys(pattern)
        if keys:
            return cache_instance.delete_many(keys)
        return 0
    
    @classmethod
    def get_or_set(cls, key: str, func, ttl: str = 'default') -> Any:
        """Get from cache or execute function and cache result"""
        value = cls.get(key)
        if value is not None:
            return value
        
        value = func()
        cls.set(key, value, ttl)
        return value
    
    @classmethod
    def clear_user_cache(cls, user_id: str):
        """Clear all cache entries for a user"""
        cls.delete_pattern(f"*:user:{user_id}:*")
    
    @classmethod
    def clear_course_cache(cls, course_id: str):
        """Clear all cache entries for a course"""
        cls.delete_pattern(f"*:course:{course_id}:*")


class DashboardCache:
    """Cache management for dashboard data"""
    
    @classmethod
    def get_teacher_dashboard(cls, teacher_id: str):
        """Get cached teacher dashboard"""
        key = CacheService.get_key('dashboard:teacher', teacher_id)
        return CacheService.get(key)
    
    @classmethod
    def set_teacher_dashboard(cls, teacher_id: str, data: dict):
        """Cache teacher dashboard"""
        key = CacheService.get_key('dashboard:teacher', teacher_id)
        CacheService.set(key, data, 'dashboard_teacher')
    
    @classmethod
    def invalidate_teacher_dashboard(cls, teacher_id: str):
        """Invalidate teacher dashboard cache"""
        key = CacheService.get_key('dashboard:teacher', teacher_id)
        CacheService.delete(key)
    
    @classmethod
    def get_student_dashboard(cls, student_id: str):
        """Get cached student dashboard"""
        key = CacheService.get_key('dashboard:student', student_id)
        return CacheService.get(key)
    
    @classmethod
    def set_student_dashboard(cls, student_id: str, data: dict):
        """Cache student dashboard"""
        key = CacheService.get_key('dashboard:student', student_id)
        CacheService.set(key, data, 'dashboard_student')
    
    @classmethod
    def invalidate_student_dashboard(cls, student_id: str):
        """Invalidate student dashboard cache"""
        key = CacheService.get_key('dashboard:student', student_id)
        CacheService.delete(key)


class RiskCache:
    """Cache management for risk data"""
    
    @classmethod
    def get_risk_distribution(cls, teacher_id: str, course_id: str = None):
        """Get cached risk distribution"""
        suffix = course_id or 'all'
        key = CacheService.get_key(f'risk:dist:{teacher_id}', suffix)
        return CacheService.get(key)
    
    @classmethod
    def set_risk_distribution(cls, teacher_id: str, data: dict, course_id: str = None):
        """Cache risk distribution"""
        suffix = course_id or 'all'
        key = CacheService.get_key(f'risk:dist:{teacher_id}', suffix)
        CacheService.set(key, data, 'risk_distribution')
    
    @classmethod
    def invalidate_risk_distribution(cls, teacher_id: str):
        """Invalidate all risk distribution caches for teacher"""
        CacheService.delete_pattern(f"*:risk:dist:{teacher_id}:*")


class DifficultyCache:
    """Cache management for difficulty data"""
    
    @classmethod
    def get_hardest_lessons(cls, teacher_id: str, limit: int = 10):
        """Get cached hardest lessons"""
        key = CacheService.get_key(f'difficulty:hardest:{teacher_id}', str(limit))
        return CacheService.get(key)
    
    @classmethod
    def set_hardest_lessons(cls, teacher_id: str, data: list, limit: int = 10):
        """Cache hardest lessons"""
        key = CacheService.get_key(f'difficulty:hardest:{teacher_id}', str(limit))
        CacheService.set(key, data, 'difficulty_ranking')
    
    @classmethod
    def invalidate_difficulty_cache(cls, course_id: str = None):
        """Invalidate difficulty caches"""
        if course_id:
            CacheService.delete_pattern(f"*:difficulty:*:course:{course_id}:*")
        else:
            CacheService.delete_pattern("*:difficulty:*")