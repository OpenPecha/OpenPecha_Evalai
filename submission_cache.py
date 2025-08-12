"""
Fast in-memory cache for submission progress tracking.
This provides instant status updates without database queries.
"""

import asyncio
import time
from typing import Dict, Optional, Any
from threading import Lock
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class CacheStatus(str, Enum):
    """Status values for cached submissions"""
    PENDING = "pending"
    PROCESSING = "processing" 
    UPLOADING = "uploading"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class SubmissionProgress:
    """Progress data structure for cached submissions"""
    submission_id: str
    status: CacheStatus
    message: str
    progress_percentage: int = 0  # 0-100
    step: str = ""  # Current step description
    error_details: Optional[str] = None
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = time.time()
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return asdict(self)
    
    def update(self, status: CacheStatus = None, message: str = None, 
               progress: int = None, step: str = None, error: str = None):
        """Update progress data"""
        if status is not None:
            self.status = status
        if message is not None:
            self.message = message
        if progress is not None:
            self.progress_percentage = max(0, min(100, progress))
        if step is not None:
            self.step = step
        if error is not None:
            self.error_details = error
        self.updated_at = time.time()

class SubmissionCache:
    """Thread-safe in-memory cache for submission progress"""
    
    def __init__(self, cleanup_interval: int = 300):  # 5 minutes
        self._cache: Dict[str, SubmissionProgress] = {}
        self._lock = Lock()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task = None
        
    def set_progress(self, submission_id: str, status: CacheStatus, 
                    message: str, progress: int = 0, step: str = "", 
                    error: str = None) -> None:
        """Set or update submission progress"""
        with self._lock:
            if submission_id in self._cache:
                self._cache[submission_id].update(
                    status=status, message=message, progress=progress, 
                    step=step, error=error
                )
            else:
                self._cache[submission_id] = SubmissionProgress(
                    submission_id=submission_id,
                    status=status,
                    message=message,
                    progress_percentage=progress,
                    step=step,
                    error_details=error
                )
            
            logger.info(f"Cache updated: {submission_id} -> {status.value} ({progress}%): {message}")
    
    def get_progress(self, submission_id: str) -> Optional[SubmissionProgress]:
        """Get submission progress from cache"""
        with self._lock:
            progress = self._cache.get(submission_id)
            if progress:
                logger.debug(f"Cache hit: {submission_id} -> {progress.status.value}")
                return progress
            logger.debug(f"Cache miss: {submission_id}")
            return None
    
    def remove_progress(self, submission_id: str) -> bool:
        """Remove submission from cache"""
        with self._lock:
            if submission_id in self._cache:
                del self._cache[submission_id]
                logger.info(f"Cache removed: {submission_id}")
                return True
            return False
    
    def get_all_active(self) -> Dict[str, SubmissionProgress]:
        """Get all active submissions (not completed/failed)"""
        with self._lock:
            return {
                sid: progress for sid, progress in self._cache.items()
                if progress.status not in [CacheStatus.COMPLETED, CacheStatus.FAILED]
            }
    
    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> int:
        """Remove old completed/failed entries"""
        current_time = time.time()
        removed_count = 0
        
        with self._lock:
            to_remove = []
            for submission_id, progress in self._cache.items():
                # Remove if old and completed/failed
                if (progress.status in [CacheStatus.COMPLETED, CacheStatus.FAILED] and
                    current_time - progress.updated_at > max_age_seconds):
                    to_remove.append(submission_id)
            
            for submission_id in to_remove:
                del self._cache[submission_id]
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cache cleanup: removed {removed_count} old entries")
        
        return removed_count
    
    def start_cleanup_task(self):
        """Start automatic cleanup task"""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
                logger.info("Cache cleanup task started")
        except RuntimeError:
            # No event loop running, will start later
            logger.info("No event loop running, cleanup task will start when FastAPI starts")
    
    async def _periodic_cleanup(self):
        """Periodic cleanup task"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self.cleanup_old_entries()
            except asyncio.CancelledError:
                logger.info("Cache cleanup task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = len(self._cache)
            by_status = {}
            for progress in self._cache.values():
                status = progress.status.value
                by_status[status] = by_status.get(status, 0) + 1
            
            return {
                "total_entries": total,
                "by_status": by_status,
                "active_submissions": len(self.get_all_active())
            }

# Global cache instance
submission_cache = SubmissionCache()

# Convenience functions
def set_submission_progress(submission_id: str, status: CacheStatus, 
                          message: str, progress: int = 0, step: str = "", 
                          error: str = None) -> None:
    """Set submission progress in global cache"""
    submission_cache.set_progress(submission_id, status, message, progress, step, error)

def get_submission_progress(submission_id: str) -> Optional[SubmissionProgress]:
    """Get submission progress from global cache"""
    return submission_cache.get_progress(submission_id)

def remove_submission_progress(submission_id: str) -> bool:
    """Remove submission from global cache"""
    return submission_cache.remove_progress(submission_id)

def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    return submission_cache.get_cache_stats()

# Initialize cleanup task when module is imported
def start_cache_cleanup():
    """Start the cleanup task for the global cache"""
    submission_cache.start_cleanup_task()
