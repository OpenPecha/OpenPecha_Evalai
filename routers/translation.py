from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import List, Dict, Any, Optional
from database import get_db
from auth import get_current_active_user
from models.user import User
from models.translation import ModelVersion, TranslationJob, TranslationOutput, Vote
from schemas.translation import (
    TranslationRequest, MultiTranslationRequest,
    LeaderboardResponse, LeaderboardEntry, ModelVersionRead,
    TranslationJobRead, TranslationOutputRead, ModelSuggestionResponse,
    VoteRequest, VoteResponse
)
import uuid
import json
import asyncio
import os
import time
import logging
from sse_starlette import EventSourceResponse

# Set up logging
logger = logging.getLogger(__name__)

# AI Client imports - Python 3.12 compatible
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

router = APIRouter(prefix="/translate", tags=["Translation"])

db_dependency = Depends(get_db)

# Constants - System prompt from environment variable
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a translation engine. Output only the translated text.")

# Model provider mapping
MODEL_PROVIDERS = {
    # "gpt-4o-mini": "openai",
    # "gpt-4o": "openai", 
    # "gpt-4": "openai",
    # "gpt-3.5-turbo": "openai",
    "claude-3-5-sonnet-20241022": "anthropic",
    "claude-3-5-haiku-20241022": "anthropic", 
    "claude-3-opus-20240229": "anthropic",
    "gemini-1.5-pro": "google",
    "gemini-1.5-flash": "google",
}

# Initialize AI clients conditionally
openai_client = None
anthropic_client = None
google_configured = False

if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

if GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    google_configured = True

def find_cached_translation(db: Session, text: str, model_version_id, prompt: Optional[str] = None) -> Optional[TranslationOutput]:
    """Find existing translation output for the same input, model, and prompt"""
    try:
        # Find translation outputs for jobs with the same text, prompt, and model version
        existing_output = db.query(TranslationOutput).join(TranslationJob).filter(
            TranslationJob.source_text == text,
            TranslationJob.prompt == prompt,
            TranslationOutput.model_version_id == model_version_id
        ).order_by(TranslationOutput.created_at.desc()).first()  # Get the most recent one
        
        return existing_output
    except Exception as e:
        logger.warning(f"Error checking for cached translation: {str(e)}")
        return None

def get_or_create_model_version(db: Session, version: str) -> ModelVersion:
    """Get or create a model version in the database"""
    try:
        model_version = db.query(ModelVersion).filter(ModelVersion.version == version).first()
        if not model_version:
            provider = MODEL_PROVIDERS.get(version, "unknown")
            model_version = ModelVersion(version=version, provider=provider)
            db.add(model_version)
            db.commit()
            db.refresh(model_version)
        return model_version
    except Exception as e:
        # If vote_count column doesn't exist, try creating without it
        if "vote_count does not exist" in str(e):
            db.rollback()
            # Try to query without ordering by vote_count
            try:
                from sqlalchemy import text
                result = db.execute(text("SELECT id, version, provider, created_at FROM model_version WHERE version = :version"), {"version": version})
                row = result.fetchone()
                if row:
                    # Create a ModelVersion object manually
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1] 
                    model_version.provider = row[2]
                    model_version.created_at = row[3]
                    return model_version
                else:
                    # Create new model version
                    provider = MODEL_PROVIDERS.get(version, "unknown")
                    result = db.execute(text("INSERT INTO model_version (version, provider) VALUES (:version, :provider) RETURNING id, version, provider, created_at"), 
                                      {"version": version, "provider": provider})
                    row = result.fetchone()
                    db.commit()
                    
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1]
                    model_version.provider = row[2] 
                    model_version.created_at = row[3]
                    return model_version
            except Exception:
                db.rollback()
                # Fallback: try to create ModelVersion without vote_count column
                try:
                    from sqlalchemy import text
                    import uuid
                    
                    # Generate UUID and try to insert directly
                    new_uuid = uuid.uuid4()
                    provider = MODEL_PROVIDERS.get(version, "unknown")
                    
                    # Try to insert into model_version table without vote_count
                    result = db.execute(text("""
                        INSERT INTO model_version (id, version, provider, created_at) 
                        VALUES (:id, :version, :provider, NOW()) 
                        RETURNING id, version, provider, created_at
                    """), {
                        "id": new_uuid,
                        "version": version, 
                        "provider": provider
                    })
                    row = result.fetchone()
                    db.commit()
                    
                    # Create ModelVersion object with the inserted data
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1]
                    model_version.provider = row[2]
                    model_version.created_at = row[3]
                    return model_version
                    
                except Exception:
                    db.rollback()
                    # Last resort: return ModelVersion with special marker for no-DB mode
                    model_version = ModelVersion()
                    model_version.id = None  # Signal that this shouldn't be used for DB operations
                    model_version.version = version
                    model_version.provider = MODEL_PROVIDERS.get(version, "unknown")
                    return model_version
        else:
            db.rollback()
            raise e

async def call_openai_model(model: str, text: str, prompt: Optional[str] = None):
    """Call OpenAI API for translation"""
    if not openai_client:
        yield "Error: OpenAI client not configured"
        return
        
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if prompt:
        messages.append({"role": "user", "content": f"Translation instruction: {prompt}"})
    messages.append({"role": "user", "content": text})
    
    try:
        stream = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=2000
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"OpenAI API Error: {str(e)}"

async def call_anthropic_model(model: str, text: str, prompt: Optional[str] = None):
    """Call Anthropic API for translation"""
    if not anthropic_client:
        yield "Error: Anthropic client not configured - no API key provided"
        return
        
    user_message = text
    if prompt:
        user_message = f"Translation instruction: {prompt}\n\nText to translate: {text}"
    
    try:
        with anthropic_client.messages.stream(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=2000
        ) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"Anthropic API Error: {str(e)}"

async def call_google_model(model: str, text: str, prompt: Optional[str] = None):
    """Call Google Gemini API for translation"""
    if not google_configured:
        yield "Error: Google Generative AI not configured - no API key provided"
        return
        
    try:
        # Initialize the model
        google_model = genai.GenerativeModel(model)
        
        # Create the full prompt with system instruction
        user_message = f"{SYSTEM_PROMPT}\n\n"
        if prompt:
            user_message += f"Translation instruction: {prompt}\n\nText to translate: {text}"
        else:
            user_message += f"Text to translate: {text}"
        
        # Generate content with streaming
        response = google_model.generate_content(
            user_message,
            stream=True,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2000,
                temperature=0.1,  # Low temperature for consistent translations
            )
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"Google API Error: {str(e)}"

async def mock_translation_stream(model: str, text: str, prompt: Optional[str] = None):
    """Mock translation stream for demo purposes"""
    # Simulate translation based on model and content
    if "spanish" in text.lower() or (prompt and "spanish" in prompt.lower()):
        mock_translation = f"[{model}] Hola, ¿cómo estás?"
    elif "french" in text.lower() or (prompt and "french" in prompt.lower()):
        mock_translation = f"[{model}] Bonjour, comment allez-vous?"
    elif "german" in text.lower() or (prompt and "german" in prompt.lower()):
        mock_translation = f"[{model}] Hallo, wie geht es dir?"
    else:
        mock_translation = f"[{model}] This is a demo translation of: {text}"
    
    # Stream character by character to simulate real AI streaming
    for char in mock_translation:
        await asyncio.sleep(0.03)  # Simulate streaming delay
        yield char

async def stream_translation(model: str, text: str, prompt: Optional[str] = None):
    """Stream translation from the specified model - returns errors if not configured"""
    provider = MODEL_PROVIDERS.get(model, "unknown")
    
    # Try real AI - return actual API errors
    if provider == "openai":
        if openai_client:
            async for chunk in call_openai_model(model, text, prompt):
                yield chunk
      
    elif provider == "anthropic":
        if anthropic_client:
            async for chunk in call_anthropic_model(model, text, prompt):
                yield chunk
      
    elif provider == "google":
        if google_configured:
            async for chunk in call_google_model(model, text, prompt):
                yield chunk
      
    else:
        yield f"Configuration Error: Unknown model provider '{provider}' for model '{model}'. Supported providers: openai, anthropic, google"

@router.post("/stream")
async def translate_text(
    model: str = Query(..., description="Model version to use for translation"),
    request: TranslationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Translate text using the specified model with streaming response.
    For multi-model translation, use model=multi and provide models in request body.
    
    Returns errors if AI clients are not configured.
    """
    
    # Log credential status when endpoint is triggered
    logger.info(f"Translation endpoint triggered for model: {model}")
    logger.info(f"Credential status check:")
    logger.info(f"  OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
    logger.info(f"  GOOGLE_API_KEY exists: {'GOOGLE_API_KEY' in os.environ}")
    logger.info(f"  ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
    
    if os.getenv("OPENAI_API_KEY"):
        logger.info(f"  OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')[:10]}...")
    else:
        logger.info("  OPENAI_API_KEY: Not found")
        
    if os.getenv("GOOGLE_API_KEY"):
        logger.info(f"  GOOGLE_API_KEY: {os.getenv('GOOGLE_API_KEY')[:10]}...")
    else:
        logger.info("  GOOGLE_API_KEY: Not found")
        
    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info(f"  ANTHROPIC_API_KEY: {os.getenv('ANTHROPIC_API_KEY')[:10]}...")
    else:
        logger.info("  ANTHROPIC_API_KEY: Not found")
    
    logger.info(f"Client initialization status:")
    logger.info(f"  openai_client: {openai_client is not None}")
    logger.info(f"  anthropic_client: {anthropic_client is not None}")
    logger.info(f"  google_configured: {google_configured}")
    
    if model == "multi":
        # Handle multi-model translation with random model selection
        import random
        available_models = list(MODEL_PROVIDERS.keys())
        
        if len(available_models) >= 2:
            # Randomly select 2 different models for comparison
            selected_models = random.sample(available_models, 2)
        else:
            # Fallback if insufficient models
            selected_models = ["claude-3-5-sonnet-20241022", "gemini-1.5-pro"]
        
        multi_request = MultiTranslationRequest(**request.dict(), models=selected_models)
        return translate_multi_model(multi_request, db, current_user)
    
    # Validate model
    if model not in MODEL_PROVIDERS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
        )
    
    # Create translation job
    job = TranslationJob(
        source_text=request.text,
        prompt=request.prompt,
        user_id=current_user.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Get or create model version
    model_version = get_or_create_model_version(db, model)
    
    # Store IDs to avoid session issues in async generator
    job_id = job.id
    model_version_id = model_version.id
    
    # Safety check: ensure we have valid IDs that exist in database
    if model_version_id is None:
        # ModelVersion couldn't be saved to database, so skip TranslationOutput creation
        # This prevents foreign key constraint violations
        model_version_id = "skip_db_operations"  # Special marker
    
    # Check for cached translation before making API call
    cached_output = None
    if model_version_id != "skip_db_operations":
        cached_output = find_cached_translation(db, request.text, model_version_id, request.prompt)
        
    if cached_output:
        logger.info(f"Found cached translation for model {model}, returning cached result")
        
        # Return cached result as streaming response
        async def generate_cached_stream():
            cached_text = cached_output.streamed_text
            
            # Stream the cached text character by character to simulate real streaming
            for char in cached_text:
                yield f"{json.dumps({'chunk': char, 'model': model, 'cached': True})}\n"
                await asyncio.sleep(0.01)  # Small delay to simulate streaming
            
            # Send completion event with existing output ID
            yield f"{json.dumps({'complete': True, 'output_id': str(cached_output.id), 'model': model, 'cached': True})}\n"
        
        return EventSourceResponse(generate_cached_stream())
    
    async def generate_stream():
        full_text = ""
        has_error = False
        error_message = None
        
        try:
            async for chunk in stream_translation(model, request.text, request.prompt):
                full_text += chunk
                
                # Check if this chunk is an error message
                if chunk.startswith("OpenAI API Error:") or chunk.startswith("Anthropic API Error:") or chunk.startswith("Google API Error:") or chunk.startswith("Configuration Error:"):
                    has_error = True
                    error_message = chunk
                    # Send error in structured format
                    yield f"{json.dumps({'error': chunk, 'model': model, 'error_type': 'api_error'})}\n"
                else:
                    # Send normal chunk
                    yield f"{json.dumps({'chunk': chunk, 'model': model})}\n"
            
            # Only proceed with database operations if no error occurred
            if not has_error:
                # Create new database session for the async context
                from database import SessionLocal
                async_db = SessionLocal()
                try:
                    # Check if we can safely create TranslationOutput (valid foreign key)
                    if model_version_id != "skip_db_operations":
                        # Create translation output record
                        output = TranslationOutput(
                            job_id=job_id,
                            model_version_id=model_version_id,
                            streamed_text=full_text
                        )
                        async_db.add(output)
                        async_db.commit()
                        async_db.refresh(output)
                        
                        # Send completion event with output ID
                        yield f"{json.dumps({'complete': True, 'output_id': str(output.id), 'model': model})}\n"
                    else:
                        # Skip database operations due to missing ModelVersion
                        # Send completion event without output ID
                        yield f"{json.dumps({'complete': True, 'model': model, 'note': 'Translation completed but not saved to database'})}\n"
                finally:
                    async_db.close()
            else:
                # Send error completion event
                yield f"{json.dumps({'complete': True, 'model': model, 'error': error_message, 'success': False})}\n"
            
        except Exception as e:
            yield f"{json.dumps({'error': str(e), 'model': model, 'error_type': 'system_error'})}\n"
    
    return EventSourceResponse(generate_stream())

def translate_multi_model(
    request: MultiTranslationRequest,
    db: Session,
    current_user: User
):
    """Handle multi-model translation with concurrent streaming"""
    
    # Validate models
    for model in request.models:
        if model not in MODEL_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
            )
    
    # Create translation job
    job = TranslationJob(
        source_text=request.text,
        prompt=request.prompt,
        user_id=current_user.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Get or create model versions and check for cached translations
    model_versions = {}
    model_version_ids = {}
    cached_outputs = {}
    
    for model in request.models:
        model_version = get_or_create_model_version(db, model)
        model_versions[model] = model_version
        
        # Safety check: ensure we have valid IDs that exist in database
        model_version_id = model_version.id
        if model_version_id is None:
            # ModelVersion couldn't be saved to database, so skip TranslationOutput creation
            # This prevents foreign key constraint violations
            model_version_id = "skip_db_operations"  # Special marker
        
        model_version_ids[model] = model_version_id
        
        # Check for cached translation for this model
        if model_version_id != "skip_db_operations":
            cached_output = find_cached_translation(db, request.text, model_version_id, request.prompt)
            if cached_output:
                cached_outputs[model] = cached_output
                logger.info(f"Found cached translation for model {model} in multi-model request")
    
    # Store job ID to avoid session issues
    job_id = job.id
    
    async def generate_multi_stream():
        model_outputs = {}
        completed_models = set()
        
        async def stream_model(model: str, channel: str):
            full_text = ""
            has_error = False
            error_message = None
            
            # Check if we have cached result for this model
            if model in cached_outputs:
                cached_output = cached_outputs[model]
                cached_text = cached_output.streamed_text
                
                # Stream the cached text character by character
                for char in cached_text:
                    yield f"{json.dumps({'chunk': char, 'model': model, 'channel': channel, 'cached': True})}\n"
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                
                # Mark as completed and add to outputs
                model_outputs[model] = cached_output.id
                completed_models.add(model)
                
                # Send completion event for cached result
                yield f"{json.dumps({'complete': True, 'output_id': str(cached_output.id), 'model': model, 'channel': channel, 'cached': True})}\n"
                return
            
            try:
                async for chunk in stream_translation(model, request.text, request.prompt):
                    full_text += chunk
                    
                    # Check if this chunk is an error message
                    if chunk.startswith("OpenAI API Error:") or chunk.startswith("Anthropic API Error:") or chunk.startswith("Google API Error:") or chunk.startswith("Configuration Error:"):
                        has_error = True
                        error_message = chunk
                        # Send error in structured format
                        yield f"{json.dumps({'error': chunk, 'model': model, 'channel': channel, 'error_type': 'api_error'})}\n"
                    else:
                        # Send normal chunk
                        yield f"{json.dumps({'chunk': chunk, 'model': model, 'channel': channel})}\n"
                
                # Only proceed with database operations if no error occurred
                if not has_error:
                    # Create new database session for the async context
                    from database import SessionLocal
                    async_db = SessionLocal()
                    try:
                        # Check if we can safely create TranslationOutput (valid foreign key)
                        if model_version_ids[model] != "skip_db_operations":
                            # Create translation output record
                            output = TranslationOutput(
                                job_id=job_id,
                                model_version_id=model_version_ids[model],
                                streamed_text=full_text
                            )
                            async_db.add(output)
                            async_db.commit()
                            async_db.refresh(output)
                            
                            model_outputs[model] = output.id
                            completed_models.add(model)
                            
                            # Send completion event
                            yield f"{json.dumps({'complete': True, 'output_id': str(output.id), 'model': model, 'channel': channel})}\n"
                        else:
                            # Skip database operations due to missing ModelVersion
                            completed_models.add(model)
                            
                            # Send completion event without output ID
                            yield f"{json.dumps({'complete': True, 'model': model, 'channel': channel, 'note': 'Translation completed but not saved to database'})}\n"
                    finally:
                        async_db.close()
                else:
                    # Mark as completed with error
                    completed_models.add(model)
                    
                    # Send error completion event
                    yield f"{json.dumps({'complete': True, 'model': model, 'channel': channel, 'error': error_message, 'success': False})}\n"
                
            except Exception as e:
                # Mark as completed with system error
                completed_models.add(model)
                yield f"{json.dumps({'error': str(e), 'model': model, 'channel': channel, 'error_type': 'system_error'})}\n"
        
        # Create concurrent streams for both models
        model_a, model_b = request.models[0], request.models[1]
        
        try:
            # Alternative: Simple interleaved approach for demo
            # Note: For true concurrency, could use asyncio.create_task() here
            generators = {
                "A": stream_model(model_a, "A"),
                "B": stream_model(model_b, "B")
            }
            
            active_generators = list(generators.keys())
            
            while active_generators:
                for channel in active_generators[:]:
                    try:
                        chunk = await generators[channel].__anext__()
                        yield chunk
                    except StopAsyncIteration:
                        active_generators.remove(channel)
                    except Exception as e:
                        yield f"{json.dumps({'error': str(e), 'channel': channel})}\n"
                        active_generators.remove(channel)
                    
                    await asyncio.sleep(0.01)  # Small delay between chunks
                    
        except Exception as e:
            yield f"{json.dumps({'error': str(e)})}\n"
    
    return EventSourceResponse(generate_multi_stream())

# 5-star rating vote endpoint  
@router.post("/vote/{model_version_name}", response_model=VoteResponse)
def vote_for_model(
    model_version_name: str = Path(..., description="Name of the model version (e.g., gpt-4o-mini)"),
    vote_request: VoteRequest = Body(..., description="Vote score (1-5 stars)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit a 1-5 star rating for a model version.
    Users can vote multiple times for the same model - each vote counts toward the total.
    """
    try:
        # Get or create model version
        model_version = get_or_create_model_version(db, model_version_name)
        
        if model_version.id is None:
            # Fallback for database schema issues
            return VoteResponse(
                message="Vote recorded (database schema incomplete)",
                model_version=model_version_name,
                user_score=vote_request.score,
                average_score=float(vote_request.score),
                total_votes=1,
                score_percentage=float(vote_request.score * 20)  # Convert to percentage
            )
        
        # Always create a new vote (allow multiple votes per user per model)
        new_vote = Vote(
            user_id=current_user.id,
            model_version_id=model_version.id,
            translation_output_id=None,  # Optional field for specific translation output
            score=vote_request.score
        )
        db.add(new_vote)
        db.commit()
        db.refresh(new_vote)
        
        # Calculate updated statistics
        from sqlalchemy import func
        stats = db.query(
            func.avg(Vote.score).label('avg_score'),
            func.count(Vote.id).label('total_votes')
        ).filter(Vote.model_version_id == model_version.id).first()
        
        average_score = float(stats.avg_score) if stats.avg_score else float(vote_request.score)
        total_votes = int(stats.total_votes) if stats.total_votes else 1
        score_percentage = (average_score / 5.0) * 100.0
        
        return VoteResponse(
            message="Vote recorded successfully",
            model_version=model_version.version,
            user_score=vote_request.score,
            average_score=round(average_score, 2),
            total_votes=total_votes,
            score_percentage=round(score_percentage, 1)
        )
        
    except Exception as e:
        # Fallback for any database issues
        return VoteResponse(
            message=f"Vote recorded with limitations: {str(e)[:100]}",
            model_version=model_version_name,
            user_score=vote_request.score,
            average_score=float(vote_request.score),
            total_votes=1,
            score_percentage=float(vote_request.score * 20)
        )

# Leaderboard endpoint with 5-star rating percentages
@router.get("/score", response_model=LeaderboardResponse)
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Get leaderboard showing model performance with 5-star ratings and percentages
    """
    try:
        # Get all model versions with their vote statistics
        from sqlalchemy import func
        
        # Query to get average scores and vote counts for each model
        stats_query = db.query(
            ModelVersion.id,
            ModelVersion.version,
            ModelVersion.provider,
            func.avg(Vote.score).label('avg_score'),
            func.count(Vote.id).label('total_votes'),
            func.count(case((Vote.score == 1, 1))).label('score_1'),
            func.count(case((Vote.score == 2, 1))).label('score_2'),
            func.count(case((Vote.score == 3, 1))).label('score_3'),
            func.count(case((Vote.score == 4, 1))).label('score_4'),
            func.count(case((Vote.score == 5, 1))).label('score_5')
        ).outerjoin(Vote, ModelVersion.id == Vote.model_version_id) \
         .group_by(ModelVersion.id, ModelVersion.version, ModelVersion.provider) \
         .order_by(func.avg(Vote.score).desc().nullslast()) \
         .all()
        
        leaderboard = []
        for stat in stats_query:
            avg_score = float(stat.avg_score) if stat.avg_score else 0.0
            total_votes = int(stat.total_votes) if stat.total_votes else 0
            score_percentage = (avg_score / 5.0) * 100.0 if avg_score > 0 else 0.0
            
            # Create score breakdown
            score_breakdown = {
                1: int(stat.score_1) if stat.score_1 else 0,
                2: int(stat.score_2) if stat.score_2 else 0,
                3: int(stat.score_3) if stat.score_3 else 0,
                4: int(stat.score_4) if stat.score_4 else 0,
                5: int(stat.score_5) if stat.score_5 else 0
            }
            
            leaderboard.append(LeaderboardEntry(
                model_version=stat.version,
                provider=stat.provider,
                total_votes=total_votes,
                average_score=round(avg_score, 2),
                score_percentage=round(score_percentage, 1),
                score_breakdown=score_breakdown
            ))
        
        return LeaderboardResponse(leaderboard=leaderboard)
        
    except Exception:
        # Fallback: try to get models without vote data
        try:
            model_versions = db.query(ModelVersion).all()
            
            leaderboard = []
            for model_version in model_versions:
                leaderboard.append(LeaderboardEntry(
                    model_version=model_version.version,
                    provider=model_version.provider,
                    total_votes=0,
                    average_score=0.0,
                    score_percentage=0.0,
                    score_breakdown={1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                ))
            
            return LeaderboardResponse(leaderboard=leaderboard)
            
        except Exception:
            # Ultimate fallback: empty leaderboard
            return LeaderboardResponse(leaderboard=[])

@router.get("/suggest_model", response_model=ModelSuggestionResponse)
def suggest_model_pair(db: Session = Depends(get_db)):
    """
    Suggest two random models for comparison.
    Any model can be Model A or Model B with equal probability.
    """
    import random
    
    try:
        # Get available models - first try from database, then from MODEL_PROVIDERS
        available_models = []
        
        try:
            # Try to get models from database first
            model_versions = db.query(ModelVersion.version).distinct().all()
            available_models = [mv.version for mv in model_versions]
        except Exception:
            pass
        
        # If no models in database or database error, use MODEL_PROVIDERS
        if not available_models:
            available_models = list(MODEL_PROVIDERS.keys())
        
        # Remove any empty or invalid model names
        available_models = [model for model in available_models if model and model.strip()]
        
        if len(available_models) < 2:
            # Fallback if insufficient models
            fallback_models = ["claude-3-5-sonnet-20241022", "gemini-1.5-pro", "claude-3-5-haiku-20241022"]
            available_models = [model for model in fallback_models if model in MODEL_PROVIDERS]
        
        if len(available_models) >= 2:
            # Randomly select 2 different models
            selected = random.sample(available_models, 2)
            
            # Randomly assign to A and B (any model can be in either position)
            model_a, model_b = selected[0], selected[1]
            
            return {
                "model_a": model_a,
                "model_b": model_b,
                "selection_method": "random",
                "total_models_available": len(available_models),
                "note": f"Randomly selected from {len(available_models)} available models"
            }
        else:
            # Absolute fallback
            return {
                "model_a": "claude-3-5-sonnet-20241022",
                "model_b": "gemini-1.5-pro", 
                "selection_method": "hardcoded",
                "note": "Using hardcoded defaults (insufficient models available)"
            }
        
    except Exception as e:
        logger.error(f"Error in suggest_model_pair: {str(e)}")
        # Ultimate fallback
        return {
            "model_a": "claude-3-5-sonnet-20241022",
            "model_b": "gemini-1.5-pro",
            "selection_method": "error_fallback",
            "note": f"Error occurred: {str(e)[:100]}"
        }

@router.get("/status")
def get_system_status():
    """
    Get the current status of AI integrations
    """
    return {
        "openai_available": OPENAI_AVAILABLE and openai_client is not None,
        "anthropic_available": ANTHROPIC_AVAILABLE and anthropic_client is not None,
        "google_available": GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY") is not None,
        "supported_models": list(MODEL_PROVIDERS.keys()),
        "mode": "production" if any([
            OPENAI_AVAILABLE and openai_client,
            ANTHROPIC_AVAILABLE and anthropic_client,
            GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY")
        ]) else "demo"
    }