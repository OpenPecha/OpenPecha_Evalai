import asyncio
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from models.submission import SubmissionStatus
from Evaluation.evaluation import trigger_automatic_evaluation
from CRUD.upload_file_to_s3 import process_json_file_upload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubmissionProcessor:
    """Handle background processing of submissions"""
    
    @staticmethod
    async def process_submission_async(
        submission_id: str,
        file_content: bytes,
        filename: str,
        user_id: str,
        model_id: str,
        challenge_name: str,
        ground_truth_url: str
    ):
        """
        Process a submission in the background:
        1. Upload file to S3
        2. Validate file format
        3. Run evaluation
        4. Update submission status
        """
        db = SessionLocal()
        try:
            logger.info(f"Starting background processing for submission {submission_id}")
            
            # Get submission instance
            submission = db.query(models.Submission).filter(
                models.Submission.id == submission_id
            ).first()
            
            if not submission:
                logger.error(f"Submission {submission_id} not found")
                return
            
            # Update status to processing
            submission.status = SubmissionStatus.PROCESSING
            submission.status_message = "Processing file upload and validation..."
            db.commit()
            
            # Process file upload and validation
            success, message, s3_url, _ = await process_json_file_upload(
                file_content, filename, user_id, model_id, submission_id, challenge_name, ground_truth_url
            )
            
            if not success:
                # Mark as failed
                submission.status = SubmissionStatus.FAILED
                submission.status_message = f"File processing failed: {message}"
                db.commit()
                logger.error(f"File processing failed for submission {submission_id}: {message}")
                return
            
            # Update submission with S3 URL
            submission.dataset_url = s3_url
            submission.status_message = "File uploaded successfully. Running evaluation..."
            db.commit()
            
            # Run evaluation
            try:
                evaluation_success = await trigger_automatic_evaluation(db, submission)
                
                if evaluation_success:
                    submission.status = SubmissionStatus.COMPLETED
                    submission.status_message = "Evaluation completed successfully"
                    logger.info(f"Evaluation completed successfully for submission {submission_id}")
                else:
                    submission.status = SubmissionStatus.FAILED
                    submission.status_message = "Evaluation failed"
                    logger.error(f"Evaluation failed for submission {submission_id}")
                
            except Exception as eval_error:
                submission.status = SubmissionStatus.FAILED
                submission.status_message = f"Evaluation error: {str(eval_error)}"
                logger.error(f"Error during evaluation for submission {submission_id}: {str(eval_error)}")
            
            # Final commit
            db.commit()
            logger.info(f"Background processing completed for submission {submission_id} with status: {submission.status}")
            
        except Exception as e:
            logger.error(f"Error in background processing for submission {submission_id}: {str(e)}")
            try:
                submission = db.query(models.Submission).filter(
                    models.Submission.id == submission_id
                ).first()
                if submission:
                    submission.status = SubmissionStatus.FAILED
                    submission.status_message = f"Processing error: {str(e)}"
                    db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update submission status: {str(db_error)}")
            
        finally:
            db.close()

# Global task tracking (in production, use Redis or similar)
running_tasks = {}

def start_submission_processing(
    submission_id: str,
    file_content: bytes,
    filename: str,
    user_id: str,
    model_id: str,
    challenge_name: str,
    ground_truth_url: str
) -> bool:
    """
    Start background processing for a submission
    
    Returns:
        True if task started successfully, False otherwise
    """
    try:
        # Check if task is already running
        if submission_id in running_tasks:
            logger.warning(f"Task for submission {submission_id} is already running")
            return False
        
        # Create and start the background task
        task = asyncio.create_task(
            SubmissionProcessor.process_submission_async(
                submission_id, file_content, filename, user_id, 
                model_id, challenge_name, ground_truth_url
            )
        )
        
        running_tasks[submission_id] = task
        
        # Clean up task when done
        def cleanup_task(task):
            if submission_id in running_tasks:
                del running_tasks[submission_id]
        
        task.add_done_callback(lambda t: cleanup_task(t))
        
        logger.info(f"Started background processing for submission {submission_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start background processing for submission {submission_id}: {str(e)}")
        return False

def get_task_status(submission_id: str) -> bool:
    """Check if a background task is still running for a submission"""
    return submission_id in running_tasks and not running_tasks[submission_id].done()
