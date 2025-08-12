"""
Queue-based worker system for non-blocking submission processing.
Uses threading and queues to ensure API endpoints remain responsive.
"""

import threading
import queue
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from models.submission import SubmissionStatus
from Evaluation.evaluation import trigger_automatic_evaluation
from CRUD.upload_file_to_s3 import process_json_file_upload
from submission_cache import (
    set_submission_progress, 
    CacheStatus
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SubmissionTask:
    """Data structure for submission processing tasks"""
    submission_id: str
    file_content: bytes
    filename: str
    user_id: str
    model_id: str
    challenge_name: str
    ground_truth_url: str
    priority: int = 0  # Lower numbers = higher priority
    
    def __lt__(self, other):
        """For priority queue ordering"""
        return self.priority < other.priority

class SubmissionWorker:
    """Worker class that processes submissions from a queue"""
    
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.is_running = False
        
    async def process_submission(self, task: SubmissionTask):
        """Process a single submission task"""
        submission_id = task.submission_id
        db = SessionLocal()
        
        try:
            logger.info(f"Worker {self.worker_id} processing submission {submission_id}")
            
            # Update cache with processing status
            set_submission_progress(
                submission_id, CacheStatus.PROCESSING, 
                f"Worker {self.worker_id} started processing...", 
                progress=10, step="Worker Started"
            )
            
            # Get submission instance
            submission = db.query(models.Submission).filter(
                models.Submission.id == submission_id
            ).first()
            
            if not submission:
                error_msg = f"Submission {submission_id} not found"
                logger.error(error_msg)
                set_submission_progress(
                    submission_id, CacheStatus.FAILED,
                    "Submission not found in database",
                    progress=0, step="Error", error=error_msg
                )
                return
            
            # Update database status
            submission.status = SubmissionStatus.PROCESSING
            submission.status_message = f"Processing by worker {self.worker_id}..."
            db.commit()
            
            # Step 1: File upload and validation
            set_submission_progress(
                submission_id, CacheStatus.UPLOADING,
                "Uploading and validating file...",
                progress=30, step="File Upload & Validation"
            )
            
            success, message, s3_url, _ = await process_json_file_upload(
                task.file_content, task.filename, task.user_id, task.model_id, 
                submission_id, task.challenge_name, task.ground_truth_url
            )
            
            if not success:
                error_msg = f"File processing failed: {message}"
                logger.error(f"Worker {self.worker_id}: {error_msg}")
                
                set_submission_progress(
                    submission_id, CacheStatus.FAILED,
                    "File upload or validation failed",
                    progress=0, step="Failed", error=error_msg
                )
                
                submission.status = SubmissionStatus.FAILED
                submission.status_message = error_msg
                db.commit()
                return
            
            # Step 2: Update submission with S3 URL
            set_submission_progress(
                submission_id, CacheStatus.PROCESSING,
                "File uploaded successfully. Starting evaluation...",
                progress=60, step="Starting Evaluation"
            )
            
            submission.dataset_url = s3_url
            submission.status_message = "File uploaded successfully. Running evaluation..."
            db.commit()
            
            # Step 3: Run evaluation
            set_submission_progress(
                submission_id, CacheStatus.EVALUATING,
                "Running automatic evaluation...",
                progress=80, step="Evaluation in Progress"
            )
            
            try:
                evaluation_success = await trigger_automatic_evaluation(db, submission)
                
                if evaluation_success:
                    set_submission_progress(
                        submission_id, CacheStatus.COMPLETED,
                        f"Evaluation completed successfully by worker {self.worker_id}",
                        progress=100, step="Completed"
                    )
                    
                    submission.status = SubmissionStatus.COMPLETED
                    submission.status_message = "Evaluation completed successfully"
                    logger.info(f"Worker {self.worker_id}: Completed submission {submission_id}")
                else:
                    error_msg = "Evaluation failed"
                    set_submission_progress(
                        submission_id, CacheStatus.FAILED,
                        error_msg,
                        progress=0, step="Failed", error="Automatic evaluation failed"
                    )
                    
                    submission.status = SubmissionStatus.FAILED
                    submission.status_message = error_msg
                    logger.error(f"Worker {self.worker_id}: Evaluation failed for {submission_id}")
                
            except Exception as eval_error:
                error_msg = f"Evaluation error: {str(eval_error)}"
                logger.error(f"Worker {self.worker_id}: {error_msg}")
                
                set_submission_progress(
                    submission_id, CacheStatus.FAILED,
                    "Evaluation error occurred",
                    progress=0, step="Failed", error=error_msg
                )
                
                submission.status = SubmissionStatus.FAILED
                submission.status_message = error_msg
            
            # Final commit
            db.commit()
            
        except Exception as e:
            error_msg = f"Worker {self.worker_id} processing error: {str(e)}"
            logger.error(error_msg)
            
            set_submission_progress(
                submission_id, CacheStatus.FAILED,
                "Unexpected processing error",
                progress=0, step="Failed", error=error_msg
            )
            
            try:
                submission = db.query(models.Submission).filter(
                    models.Submission.id == submission_id
                ).first()
                if submission:
                    submission.status = SubmissionStatus.FAILED
                    submission.status_message = error_msg
                    db.commit()
            except Exception as db_error:
                logger.error(f"Worker {self.worker_id}: Failed to update submission status: {db_error}")
        
        finally:
            db.close()
    
    def run(self, task_queue: queue.Queue):
        """Main worker loop - runs in separate thread"""
        self.is_running = True
        logger.info(f"Worker {self.worker_id} started")
        
        while self.is_running:
            try:
                # Get task from queue (blocks until available)
                task = task_queue.get(timeout=5)  # 5 second timeout
                
                if task is None:  # Shutdown signal
                    break
                
                # Process the task
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.process_submission(task))
                finally:
                    loop.close()
                
                # Mark task as done
                task_queue.task_done()
                
            except queue.Empty:
                # Timeout occurred, continue loop
                continue
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                try:
                    task_queue.task_done()
                except Exception:
                    pass
        
        logger.info(f"Worker {self.worker_id} stopped")
    
    def stop(self):
        """Stop the worker"""
        self.is_running = False

class SubmissionQueue:
    """Manages the submission processing queue and workers"""
    
    def __init__(self, num_workers: int = 2):
        self.task_queue = queue.Queue()
        self.workers = []
        self.worker_threads = []
        self.num_workers = num_workers
        self._stats = {
            "total_queued": 0,
            "total_processed": 0,
            "queue_size": 0
        }
    
    def start_workers(self):
        """Start all worker threads"""
        for i in range(self.num_workers):
            worker = SubmissionWorker(worker_id=i+1)
            thread = threading.Thread(
                target=worker.run, 
                args=(self.task_queue,),
                daemon=True,
                name=f"SubmissionWorker-{i+1}"
            )
            
            self.workers.append(worker)
            self.worker_threads.append(thread)
            thread.start()
            
        logger.info(f"Started {self.num_workers} submission workers")
    
    def add_task(self, task: SubmissionTask) -> bool:
        """Add a task to the processing queue"""
        try:
            self.task_queue.put(task)
            self._stats["total_queued"] += 1
            self._stats["queue_size"] = self.task_queue.qsize()
            
            logger.info(f"Task queued: {task.submission_id} (queue size: {self._stats['queue_size']})")
            return True
        except Exception as e:
            logger.error(f"Failed to queue task {task.submission_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        self._stats["queue_size"] = self.task_queue.qsize()
        self._stats["active_workers"] = len([w for w in self.workers if w.is_running])
        return self._stats.copy()
    
    def stop_workers(self):
        """Stop all workers"""
        logger.info("Stopping submission workers...")
        
        # Send shutdown signals
        for _ in self.workers:
            self.task_queue.put(None)
        
        # Stop workers
        for worker in self.workers:
            worker.stop()
        
        # Wait for threads to finish
        for thread in self.worker_threads:
            thread.join(timeout=10)
        
        logger.info("All submission workers stopped")

# Global queue instance
submission_queue = SubmissionQueue(num_workers=2)

def start_submission_workers():
    """Start the submission processing workers"""
    submission_queue.start_workers()

def queue_submission_for_processing(
    submission_id: str,
    file_content: bytes,
    filename: str,
    user_id: str,
    model_id: str,
    challenge_name: str,
    ground_truth_url: str,
    priority: int = 0
) -> bool:
    """Queue a submission for processing"""
    task = SubmissionTask(
        submission_id=submission_id,
        file_content=file_content,
        filename=filename,
        user_id=user_id,
        model_id=model_id,
        challenge_name=challenge_name,
        ground_truth_url=ground_truth_url,
        priority=priority
    )
    
    return submission_queue.add_task(task)

def get_queue_stats() -> Dict[str, Any]:
    """Get submission queue statistics"""
    return submission_queue.get_stats()

def stop_submission_workers():
    """Stop all submission workers"""
    submission_queue.stop_workers()
