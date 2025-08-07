import json
import requests
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import models
from models.result import ResultType
import logging
import os
from dotenv import load_dotenv
import pyewts
from evaluate import load

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def download_json_from_s3(s3_url: str) -> Optional[List[Dict]]:
    """
    Download JSON file from S3 URL using direct HTTP request.
    
    Args:
        s3_url: S3 URL of the JSON file
        
    Returns:
        List of dictionaries containing the JSON data, or None if error
    """
    try:
        # Download file directly via HTTP
        # Disable SSL verification for S3 URLs to avoid certificate issues with custom bucket names
        verify_ssl = False if 'amazonaws.com' in s3_url else True
        response = requests.get(s3_url, timeout=30, verify=verify_ssl)
        response.raise_for_status()  # Raises exception for bad status codes
        
        # Parse JSON directly from response
        json_data = response.json()
        
        # Ensure we return a list
        if isinstance(json_data, list):
            return json_data
        else:
            return [json_data]
            
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error downloading {s3_url}: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error for {s3_url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading {s3_url}: {str(e)}")
        return None

def evaluator(challenge_data: List[Dict], submission_data: List[Dict]) -> Dict[str, float]:
    """
    Calculate CER and WER metrics for Tibetan text using Wylie transliteration.
    
    Args:
        challenge_data: List of dicts with 'filename' and 'label' (ground truth)
        submission_data: List of dicts with 'filename' and 'prediction' (model predictions)
        
    Returns:
        Dictionary with 'cer' and 'wer' scores
    """
    try:
        # Initialize Wylie converter and scorers
        converter = pyewts.pyewts()
        cer_scorer = load("cer")
        wer_scorer = load("wer")
        
        # Create dictionaries for quick lookup
        challenge_dict = {item['filename']: item['label'] for item in challenge_data}
        submission_dict = {item['filename']: item['prediction'] for item in submission_data}
        
        # Find common filenames
        common_files = set(challenge_dict.keys()) & set(submission_dict.keys())
        
        if not common_files:
            logger.warning("No common files found between challenge and submission data")
            return {'cer': 1.0, 'wer': 1.0}  # Return worst possible scores
        
        # Check for missing/extra files
        missing_in_pred = set(challenge_dict.keys()) - set(submission_dict.keys())
        if missing_in_pred:
            logger.warning(f"Missing predictions for {len(missing_in_pred)} files: {sorted(list(missing_in_pred))}")
        
        extra_in_pred = set(submission_dict.keys()) - set(challenge_dict.keys())
        if extra_in_pred:
            logger.warning(f"Extra predictions for {len(extra_in_pred)} files not in ground truth: {sorted(list(extra_in_pred))}")
        
        logger.info(f"Found {len(common_files)} common files for evaluation")
        
        cer_scores = []
        wer_scores = []
        
        for filename in common_files:
            reference = challenge_dict[filename].strip()
            prediction = submission_dict[filename].strip()
            
            # Skip empty labels or predictions
            if not reference or not prediction:
                logger.warning(f"Skipping empty label or prediction for {filename}")
                continue
            
            # Convert both label and prediction to Wylie transliteration
            try:
                reference_wylie = converter.toWylie(reference)
                prediction_wylie = converter.toWylie(prediction)
                
                # Calculate CER for this file pair
                cer_score = cer_scorer.compute(predictions=[prediction_wylie], references=[reference_wylie])
                cer_scores.append(cer_score)
                
                # Calculate WER for this file pair
                wer_score = wer_scorer.compute(predictions=[prediction_wylie], references=[reference_wylie])
                wer_scores.append(wer_score)
                    
            except Exception as e:
                logger.error(f"Failed to process {filename}: {str(e)}")
                continue
        
        if len(cer_scores) == 0:
            logger.warning("No valid files could be evaluated")
            return {'cer': 1.0, 'wer': 1.0}  # Set max scores if nothing evaluated
        
        # Calculate mean CER and WER
        mean_cer = sum(cer_scores) / len(cer_scores)
        mean_wer = sum(wer_scores) / len(wer_scores)
        
        logger.info(f"Evaluated {len(cer_scores)} samples")
        logger.info(f"Mean CER: {mean_cer:.4f}")
        logger.info(f"Mean WER: {mean_wer:.4f}")
        
        return {
            'cer': float(round(mean_cer, 4)),
            'wer': float(round(mean_wer, 4))
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in Tibetan evaluation: {str(e)}")
        return {'cer': 1.0, 'wer': 1.0}

async def evaluate(challenge_data_url: str, submission_data_url: str, evaluator_func=evaluator) -> Optional[Dict[str, float]]:
    """
    Main evaluation function that downloads data and runs evaluation.
    
    Args:
        challenge_data_url: S3 URL of the challenge ground truth JSON
        submission_data_url: S3 URL of the submission predictions JSON
        evaluator_func: Function to use for evaluation (default: evaluator)
        
    Returns:
        Dictionary with evaluation results or None if error
    """
    try:
        logger.info(f"Starting evaluation: challenge={challenge_data_url}, submission={submission_data_url}")
        
        # Download challenge data
        challenge_data = await download_json_from_s3(challenge_data_url)
        if challenge_data is None:
            logger.error("Failed to download challenge data")
            return None
        
        # Download submission data
        submission_data = await download_json_from_s3(submission_data_url)
        if submission_data is None:
            logger.error("Failed to download submission data")
            return None
        
        # Run evaluation
        results = evaluator_func(challenge_data, submission_data)
        
        logger.info(f"Evaluation completed successfully: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in evaluate function: {str(e)}")
        return None

async def trigger_automatic_evaluation(db: Session, submission_instance: models.Submission) -> bool:
    """
    Trigger automatic evaluation for a submission and save results to database.
    
    Args:
        db: Database session
        submission_instance: The submission instance to evaluate
        
    Returns:
        True if evaluation succeeded, False otherwise
    """
    try:
        logger.info(f"Starting automatic evaluation for submission {submission_instance.id}")
        
        # Get challenge instance to fetch ground truth URL
        challenge_instance = db.query(models.Challenge).filter(
            models.Challenge.id == submission_instance.challenge_id
        ).first()
        
        if not challenge_instance:
            logger.error(f"Challenge not found for submission {submission_instance.id}")
            return False
        
        if not challenge_instance.ground_truth:
            logger.error(f"No ground truth URL found for challenge {challenge_instance.id}")
            return False
        
        if not submission_instance.dataset_url:
            logger.error(f"No dataset URL found for submission {submission_instance.id}")
            return False
        
        # Run evaluation
        evaluation_results = await evaluate(
            challenge_instance.ground_truth,
            submission_instance.dataset_url
        )
        
        if evaluation_results is None:
            logger.error(f"Evaluation failed for submission {submission_instance.id}")
            return False
        
        # Save results to database
        success = await save_evaluation_results(
            db, 
            submission_instance.user_id,
            submission_instance.id,
            evaluation_results
        )
        
        if success:
            logger.info(f"Automatic evaluation completed successfully for submission {submission_instance.id}")
        else:
            logger.error(f"Failed to save evaluation results for submission {submission_instance.id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error in trigger_automatic_evaluation: {str(e)}")
        return False

async def save_evaluation_results(db: Session, user_id: str, submission_id: str, results: Dict[str, float]) -> bool:
    """
    Save evaluation results to the Result table.
    
    Args:
        db: Database session
        user_id: ID of the user who made the submission
        submission_id: ID of the submission
        results: Dictionary containing 'cer' and 'wer' scores
        
    Returns:
        True if save succeeded, False otherwise
    """
    try:
        # Create CER result record
        cer_result = models.Result(
            type=ResultType.CER.value,
            user_id=user_id,
            submission_id=submission_id,
            score=round(results['cer'], 4),  # Round to 4 decimal places
            created_by='system',
            updated_by='system'
        )
        
        # Create WER result record
        wer_result = models.Result(
            type=ResultType.WER.value,
            user_id=user_id,
            submission_id=submission_id,
            score=round(results['wer'], 4),  # Round to 4 decimal places
            created_by='system',
            updated_by='system'
        )
        
        # Add to database
        db.add(cer_result)
        db.add(wer_result)
        db.commit()
        
        logger.info(f"Saved evaluation results: CER={results['cer']:.4f}, WER={results['wer']:.4f}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving evaluation results: {str(e)}")
        db.rollback()
        return False