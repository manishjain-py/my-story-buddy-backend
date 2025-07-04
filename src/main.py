import os
import logging
import time
import json
import asyncio
import base64
import uuid
import traceback
from datetime import datetime
from io import BytesIO

import httpx
import boto3
import botocore
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from PIL import Image

# Import authentication modules (required for proper functionality)
from auth.auth_routes import auth_router
from auth.auth_models import UserDatabase
from auth.auth_utils import get_optional_user, get_current_user
from core.database import db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="My Story Buddy API",
    description="API for generating stories and user authentication",
    version="2.0.0",
    docs_url=None,
    redoc_url=None
)

# Include authentication routes
app.include_router(auth_router)
logger.info("Authentication routes included")

# Configure CORS for production and development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=False,  # Must be False when using "*"
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Startup event to initialize database (if available)
@app.on_event("startup")
async def startup_event():
    """Initialize database and create tables on startup"""
    try:
        logger.info("Starting My Story Buddy API...")
        
        # Set Google OAuth credentials if not already set
        if not os.getenv('GOOGLE_CLIENT_ID'):
            os.environ['GOOGLE_CLIENT_ID'] = '61667042929-m5fsbphfu1the98ots0agfdr75pqa7c7.apps.googleusercontent.com'
            logger.info("Google OAuth Client ID set from configuration")
        
        if not os.getenv('GOOGLE_CLIENT_SECRET'):
            os.environ['GOOGLE_CLIENT_SECRET'] = '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'
            logger.info("Google OAuth Client Secret set from configuration")
        
        if not os.getenv('GOOGLE_REDIRECT_URI'):
            os.environ['GOOGLE_REDIRECT_URI'] = 'http://127.0.0.1:8003/auth/google/callback'
            logger.info("Google OAuth Redirect URI set from configuration")
        
        if not os.getenv('FRONTEND_URL'):
            os.environ['FRONTEND_URL'] = 'http://localhost:3000'
            logger.info("Frontend URL set from configuration")
        
        # Initialize database connection (required - will fail if not available)
        await db_manager.initialize()
        
        # Create all tables
        from core.database import create_tables
        await create_tables()
        
        # Create authentication tables
        await UserDatabase.create_user_tables()
        
        logger.info("Database initialized successfully!")
        
        logger.info("My Story Buddy API is ready!")
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        # Don't fail startup if database is unavailable
        logger.warning("API started without database connectivity")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        if current_user and db_manager:
            await db_manager.close()
            logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

# Health check endpoint for Lambda testing
@app.get("/health")
async def health_check():
    """Health check endpoint to verify the application is working"""
    return {
        "status": "healthy",
        "message": "My Story Buddy API is running with automated CI/CD",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
        "environment": "ec2" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") is None else "lambda",
        "deployment": "automated-pipeline",
        "uptime": datetime.now().isoformat()
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint for quick health checks"""
    return {"message": "pong"}

# Constants
S3_BUCKET = "mystorybuddy-assets"

# Initialize clients
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize S3 client
try:
    s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    try:
        s3_client.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        logger.info(f"Successfully connected to AWS S3 bucket: {S3_BUCKET}")
    except Exception as e:
        logger.warning(f"Could not verify bucket access: {str(e)}")
        logger.warning("Continuing with S3 client initialization...")
except Exception as e:
    logger.warning(f"Failed to initialize S3 client: {str(e)}")
    logger.warning("S3 functionality will be disabled. Images will not be saved.")
    logger.warning("To enable S3 functionality, ensure AWS credentials have proper permissions:")
    logger.warning("1. AWS CLI: aws configure")
    logger.warning("2. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    logger.warning("3. AWS credentials file: ~/.aws/credentials")
    logger.warning(f"4. Required permissions: s3:PutObject, s3:GetObject on bucket: {S3_BUCKET}")
    s3_client = None

# Models
class StoryRequest(BaseModel):
    prompt: str = ""
    formats: list[str] = ["Comic Book", "Text Story"]

class StoryResponse(BaseModel):
    title: str
    story: str
    image_urls: list[str]

class FunFactRequest(BaseModel):
    prompt: str = ""

class FunFact(BaseModel):
    question: str
    answer: str

class FunFactsResponse(BaseModel):
    facts: list[FunFact]

class AsyncStoryResponse(BaseModel):
    story_id: int
    status: str
    message: str

class StoryStatusResponse(BaseModel):
    story_id: int
    status: str
    title: str
    story: str
    image_urls: list[str]
    created_at: str
    updated_at: str

class AvatarResponse(BaseModel):
    id: int
    avatar_name: str
    traits_description: str
    s3_image_url: str
    created_at: str
    updated_at: str

class AvatarUpdateRequest(BaseModel):
    avatar_name: str = None
    traits_description: str = None

# Helper functions
def cors_error_response(message: str, status_code: int = 500):
    return JSONResponse(
        status_code=status_code,
        content={"detail": message},
        headers={
            "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

def log_request_details(request: Request, request_id: str):
    """Log detailed information about the incoming request."""
    logger.info(f"Request ID: {request_id}")
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    logger.info(f"Request Client: {request.client.host if request.client else 'Unknown'}")

def log_error(error: Exception, request_id: str):
    """Log detailed error information."""
    logger.error(f"Request ID: {request_id} - Error occurred")
    logger.error(f"Error Type: {type(error).__name__}")
    logger.error(f"Error Message: {str(error)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

async def save_image_to_s3(image_bytes: bytes, content_type: str = "image/png", request_id: str = None, image_index: int = None) -> str:
    """Save image bytes to S3 and return the URL."""
    if s3_client is None:
        logger.warning(f"Request ID: {request_id} - S3 client not initialized, skipping image upload")
        return "https://via.placeholder.com/400x300?text=Image+Upload+Disabled"
    
    if not image_bytes:
        logger.error(f"Request ID: {request_id} - No image bytes provided")
        return "https://via.placeholder.com/400x300?text=No+Image+Data"
        
    try:
        start_time = time.time()
        logger.info(f"Request ID: {request_id} - Starting S3 upload")
        
        if image_index is not None:
            object_key = f"stories/{request_id}_image_{image_index}.png"
        else:
            object_key = f"stories/{uuid.uuid4()}.png"
        logger.info(f"Request ID: {request_id} - Generated object key: {object_key}")
        
        await asyncio.to_thread(
            s3_client.put_object,
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type
        )
        
        # Use direct S3 URL since bucket is publicly readable for stories
        image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{object_key}"
        
        upload_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Image saved to S3: {image_url}")
        logger.info(f"Request ID: {request_id} - S3 upload completed in {upload_time:.2f} seconds")
        return image_url
        
    except Exception as e:
        log_error(e, request_id)
        if isinstance(e, botocore.exceptions.NoCredentialsError):
            raise HTTPException(
                status_code=500,
                detail="AWS credentials not configured. Please check the server logs for setup instructions."
            )
        elif isinstance(e, botocore.exceptions.ClientError):
            raise HTTPException(
                status_code=500,
                detail=f"AWS S3 error: {str(e)}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save image: {str(e)}"
            )

async def generate_story_images(story: str, title: str, request_id: str, original_prompt: str = "") -> list[str]:
    """Generate 4 separate 4-panel comic images for the story and return list of URLs."""
    image_urls = []
    
    # Check if this is a dev/testing request
    if "(dev)" in original_prompt.lower():
        logger.info(f"Request ID: {request_id} - Dev mode detected, returning static test images")
        dev_image_urls = [
            "https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/stories/f5ef3161-7410-4770-a7d3-6cdadeb21437_image_1.png",
            "https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/stories/f5ef3161-7410-4770-a7d3-6cdadeb21437_image_2.png",
            "https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/stories/f5ef3161-7410-4770-a7d3-6cdadeb21437_image_3.png",
            "https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/stories/f5ef3161-7410-4770-a7d3-6cdadeb21437_image_4.png"
        ]
        logger.info(f"Request ID: {request_id} - Returning {len(dev_image_urls)} static dev images")
        return dev_image_urls
    
    # Use LLM to intelligently break down the story into 4 comic parts
    logger.info(f"Request ID: {request_id} - Breaking down story into 4 comic parts...")
    breakdown_start_time = time.time()
    
    breakdown_system_prompt = (
        "You are an expert in comic storytelling and visual narrative structure. "
        "Break down the given story into exactly 4 meaningful parts for a 4-panel comic series. "
        "Each part should represent a clear story beat that works well visually. "
        "Follow classic story structure: Setup, Development, Climax, Resolution. "
        "\n\n"
        "Format your response as exactly 4 parts separated by '---PART BREAK---' like this:\n"
        "Part 1 content here\n"
        "---PART BREAK---\n"
        "Part 2 content here\n"
        "---PART BREAK---\n" 
        "Part 3 content here\n"
        "---PART BREAK---\n"
        "Part 4 content here\n"
        "\n"
        "Guidelines:\n"
        "- Part 1: Introduction and setup (characters, setting, initial situation)\n"
        "- Part 2: Development and adventure beginning (action starts, journey begins)\n"
        "- Part 3: Challenge or climax (main conflict, problem to solve, exciting moment)\n"
        "- Part 4: Resolution and conclusion (problem solved, happy ending)\n"
        "- Each part should be visually interesting and work well as a comic panel\n"
        "- Maintain the story's flow and key plot points\n"
        "- Keep the language and tone appropriate for children aged 3-5"
    )
    
    breakdown_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": breakdown_system_prompt},
            {"role": "user", "content": f"Break down this story into 4 comic parts:\n\n{story}"}
        ],
        max_tokens=800,
        temperature=0.3
    )
    
    breakdown_content = breakdown_response.choices[0].message.content
    breakdown_time = time.time() - breakdown_start_time
    logger.info(f"Request ID: {request_id} - Story breakdown completed in {breakdown_time:.2f} seconds")
    
    # Parse the breakdown response
    story_parts = breakdown_content.split('---PART BREAK---')
    story_parts = [part.strip() for part in story_parts if part.strip()]
    
    # Ensure we have exactly 4 parts
    if len(story_parts) != 4:
        logger.warning(f"Request ID: {request_id} - Expected 4 story parts, got {len(story_parts)}. Using fallback breakdown.")
        # Fallback to simple paragraph-based breakdown
        story_paragraphs = [p.strip() for p in story.split('\n\n') if p.strip() and not p.strip().startswith('The End!')]
        paragraphs_per_part = max(1, len(story_paragraphs) // 4)
        story_parts = []
        for i in range(4):
            start_idx = i * paragraphs_per_part
            end_idx = min(start_idx + paragraphs_per_part, len(story_paragraphs))
            if i == 3:  # Last part gets remaining paragraphs
                end_idx = len(story_paragraphs)
            story_part = '\n\n'.join(story_paragraphs[start_idx:end_idx])
            story_parts.append(story_part)
    
    logger.info(f"Request ID: {request_id} - Successfully created {len(story_parts)} story parts for comic generation")
    
    # Use the same title for all comic pages for consistency
    image_titles = [title, title, title, title]
    
    # Generate character consistency guide using stored avatar references
    logger.info(f"Request ID: {request_id} - Generating character consistency guide...")
    consistency_start_time = time.time()
    
    # Extract character references from the enriched prompt
    character_references = ""
    if "CHARACTER DETAILS FOR" in original_prompt:
        try:
            logger.info(f"Request ID: {request_id} - Found CHARACTER DETAILS in prompt, extracting references...")
            # Log a snippet of the prompt for debugging
            char_detail_start = original_prompt.find("CHARACTER DETAILS FOR")
            prompt_snippet = original_prompt[char_detail_start:char_detail_start+200] if char_detail_start != -1 else "Not found"
            logger.info(f"Request ID: {request_id} - Prompt snippet: {prompt_snippet}")
            
            # Extract all character reference cards from the enriched prompt
            import re
            # More flexible pattern to handle different formatting
            character_sections = re.findall(r'CHARACTER DETAILS FOR\s+([^:\n]+):\s*(.*?)(?=CHARACTER DETAILS FOR|$)', original_prompt, re.DOTALL)
            
            if character_sections:
                character_references = "\n\n=== STORED CHARACTER REFERENCES ===\n"
                for char_name, char_details in character_sections:
                    character_references += f"\nCHARACTER: {char_name.strip()}\n{char_details.strip()}\n"
                character_references += "\n=== END CHARACTER REFERENCES ===\n"
                logger.info(f"Request ID: {request_id} - Found {len(character_sections)} character reference(s) for consistency")
            else:
                logger.info(f"Request ID: {request_id} - No character sections matched the pattern, using fallback")
                # Fall back to including the entire character section
                if "Personality:" in original_prompt or "Appearance:" in original_prompt:
                    character_references = f"\n\n=== CHARACTER INFORMATION ===\n{original_prompt[char_detail_start:]}\n=== END CHARACTER INFO ===\n"
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Error extracting character references: {str(e)}")
            # Fall back to simple character detection
            if "Personality:" in original_prompt or "Appearance:" in original_prompt:
                character_references = f"\n\n=== CHARACTER INFORMATION ===\n{original_prompt}\n=== END CHARACTER INFO ===\n"
    
    consistency_system_prompt = (
        "You are an expert comic book artist specializing in character consistency. "
        "Create a comprehensive visual style guide that ensures PERFECT consistency across multiple comic panels. "
        "If character references are provided, use them EXACTLY as the definitive character descriptions. "
        "Focus on maintaining identical character appearances, color palettes, and art style throughout all panels."
    )
    
    consistency_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": consistency_system_prompt},
            {"role": "user", "content": f"""Create a detailed visual consistency guide for this story:

STORY:
{story}

{character_references}

REQUIREMENTS:
- If character references are provided above, use them EXACTLY for character appearances
- Create consistent art style notes for all characters and scenes
- Specify color palettes that must remain identical across all panels
- Note distinctive features that must appear in every panel featuring each character
- Ensure the comic style is cute, child-friendly, and visually consistent"""}
        ],
        max_tokens=600,
        temperature=0.1
    )
    
    character_guide = consistency_response.choices[0].message.content
    consistency_time = time.time() - consistency_start_time
    logger.info(f"Request ID: {request_id} - Character guide generated in {consistency_time:.2f} seconds")

    # Generate all 4 images in parallel with consistency guide
    logger.info(f"Request ID: {request_id} - Generating 4 comic images in parallel...")
    parallel_start_time = time.time()
    
    async def generate_single_image(index: int, story_part: str, image_title: str) -> tuple[int, str]:
        """Generate a single 4-panel comic image."""
        try:
            logger.info(f"Request ID: {request_id} - Starting generation for image {index+1}/4...")
            
            visual_prompt = f'''
Create a 4-panel comic-style illustration for "{title}".

STORY CONTENT:
{story_part}

CHARACTER & STYLE CONSISTENCY GUIDE:
{character_guide}

🎯 CRITICAL CHARACTER CONSISTENCY REQUIREMENTS:
- Follow the character descriptions EXACTLY as specified in the consistency guide
- If any named characters appear, they must match their reference descriptions PERFECTLY
- Use the EXACT same facial features, hair, clothing, and distinctive marks
- Maintain IDENTICAL color palettes for each character across all panels
- Character proportions and art style must be consistent with previous images

LAYOUT:
- Create exactly 4 panels in a 2x2 grid layout
- Panel arrangement: [Panel 1] [Panel 2]
                     [Panel 3] [Panel 4]
- Each panel progresses the story section sequentially

VISUAL REQUIREMENTS:
- IDENTICAL character designs as specified in the consistency guide
- SAME art style, colors, and visual elements as the guide
- Use cute, friendly characters with big eyes and gentle expressions
- Soft pastel colors and storybook-like visual style
- Keep tone gentle, magical, and fun
- Match this reference style: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/PHOTO-2025-06-09-11-37-16.jpg

CHARACTER VERIFICATION:
- Before generating, verify each character matches their reference description
- Pay special attention to: facial features, hair color/style, clothing, accessories
- Ensure any named characters are instantly recognizable from their reference cards
- Maintain character personality through expressions and body language

STORY PROGRESSION:
- Show this story section across all 4 panels
- Include speech bubbles or captions where appropriate
- Clear visual storytelling suitable for children aged 3-5
- Maintain narrative flow within the 4 panels

CONSISTENCY REMINDER: This is image {index+1} of 4 in the story series - characters must look IDENTICAL to the consistency guide and other images.
'''
            
            image_response = await client.images.generate(
                model="gpt-image-1",
                prompt=visual_prompt,
                n=1
            )
            
            image_base64 = image_response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)
            
            # Save to S3
            image_url = await save_image_to_s3(image_bytes, request_id=request_id, image_index=index+1)
            
            logger.info(f"Request ID: {request_id} - Image {index+1}/4 generated and saved successfully")
            return index, image_url
            
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Error generating image {index+1}: {str(e)}")
            logger.error(f"Request ID: {request_id} - Error type: {type(e).__name__}")
            logger.error(f"Request ID: {request_id} - Full traceback: {traceback.format_exc()}")
            
            # Check if it's an OpenAI API error
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                logger.error(f"Request ID: {request_id} - OpenAI API status code: {e.response.status_code}")
            
            return index, "https://via.placeholder.com/400x300?text=Comic+Generation+Failed"

    # Create tasks for all 4 images
    tasks = [
        generate_single_image(i, story_part, image_title) 
        for i, (story_part, image_title) in enumerate(zip(story_parts, image_titles))
    ]
    
    # Wait for all images to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    parallel_time = time.time() - parallel_start_time
    logger.info(f"Request ID: {request_id} - All 4 images generated in parallel in {parallel_time:.2f} seconds")
    
    # Sort results by index and extract URLs
    image_urls = [""] * 4
    successful_images = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Request ID: {request_id} - Image generation task failed: {str(result)}")
            continue
            
        index, url = result
        image_urls[index] = url
        if not url.startswith("https://via.placeholder.com"):
            successful_images += 1
    
    # Fill any missing URLs with placeholders
    for i, url in enumerate(image_urls):
        if not url:
            image_urls[i] = "https://via.placeholder.com/400x300?text=Comic+Generation+Failed"
    
    logger.info(f"Request ID: {request_id} - Successfully generated {successful_images}/4 images")
    
    return image_urls

async def detect_avatar_names_in_prompt(prompt: str, user_id: int) -> dict:
    """
    Detect avatar names mentioned in the story prompt and fetch their traits.
    Returns dict with avatar names as keys and their data as values.
    """
    if not user_id:
        return {}
    
    try:
        # Get user's avatar to check if their name is mentioned
        from core.database import get_user_avatar
        avatar_data = await get_user_avatar(user_id)
        
        if not avatar_data:
            return {}
        
        avatar_name = avatar_data.get('avatar_name', '').strip()
        if not avatar_name:
            return {}
        
        # Simple name detection - check if avatar name appears in prompt (case-insensitive)
        prompt_lower = prompt.lower()
        avatar_name_lower = avatar_name.lower()
        
        if avatar_name_lower in prompt_lower:
            logger.info(f"Detected avatar '{avatar_name}' mentioned in story prompt")
            return {avatar_name: avatar_data}
        
        return {}
        
    except Exception as e:
        logger.error(f"Error detecting avatar names in prompt: {str(e)}")
        return {}

async def enrich_prompt_with_avatar_traits(prompt: str, detected_avatars: dict) -> str:
    """
    Enrich the story prompt with visual and personality traits from detected avatars.
    """
    if not detected_avatars:
        return prompt
    
    try:
        enrichment_parts = []
        
        for avatar_name, avatar_data in detected_avatars.items():
            # Build enrichment text
            enrichment = f"\n\nCHARACTER DETAILS FOR {avatar_name}:\n"
            
            # Add personality traits
            if avatar_data.get('traits_description'):
                enrichment += f"Personality: {avatar_data['traits_description']}\n"
            
            # Add visual traits if available
            if avatar_data.get('visual_traits'):
                enrichment += f"Appearance: {avatar_data['visual_traits']}\n"
            
            enrichment += f"Please ensure {avatar_name} appears in the story with these specific traits and characteristics."
            enrichment_parts.append(enrichment)
        
        # Combine original prompt with enrichment
        enriched_prompt = prompt + "\n".join(enrichment_parts)
        
        logger.info(f"Enriched prompt with {len(detected_avatars)} avatar(s): {list(detected_avatars.keys())}")
        return enriched_prompt
        
    except Exception as e:
        logger.error(f"Error enriching prompt with avatar traits: {str(e)}")
        return prompt

async def generate_story_background_task(story_id: int, prompt: str, formats: list, request_id: str, user_id: str = None):
    """Background task to generate story content and update database."""
    try:
        logger.info(f"Request ID: {request_id} - Starting background story generation for story_id: {story_id}")
        
        # Detect avatars mentioned in the prompt and enrich with their traits
        detected_avatars = {}
        enriched_prompt = prompt
        
        if user_id:
            detected_avatars = await detect_avatar_names_in_prompt(prompt, user_id)
            if detected_avatars:
                enriched_prompt = await enrich_prompt_with_avatar_traits(prompt, detected_avatars)
                logger.info(f"Request ID: {request_id} - Using enriched prompt with avatar details")
            else:
                logger.info(f"Request ID: {request_id} - No avatars detected in prompt")
        
        # Generate story content with enriched prompt
        if not enriched_prompt.strip():
            logger.info(f"Request ID: {request_id} - Using default prompt")
            system_prompt = (
                "You are a friendly and imaginative storyteller who creates elaborate, exciting, "
                "and engaging stories for children aged 3 to 5 years. "
                "Create a completely original and creative adventure story with fun elements, "
                "twists and turns that would delight and excite young children. "
                "Use simple words that a 3-5 year old can understand. "
                "Keep sentences short and clear but create an exciting narrative arc. "
                "Include characters that go on adventures, face challenges, and discover wonderful things. "
                "Make the story fun and interesting, with animals, toys, magical creatures, or fantasy elements. "
                "Add gentle humor, surprises, and exciting moments to keep children engaged throughout. "
                "The story should be approximately 200-250 words and feel like an exciting adventure "
                "meant to be read aloud to young children. "
                "Include multiple scenes and story progression with clear beginning, middle, and end. "
                "Always end the story with 'The End! (Created By - MyStoryBuddy)' on a new line. "
                "Format your response exactly like this:\n"
                "Title: [Your Title]\n\n"
                "[Story content with multiple paragraphs]\n\n"
                "The End! (Created By - MyStoryBuddy)\n\n"
                "Use double line breaks between paragraphs. Create 8-12 paragraphs to tell the full adventure."
            )
            user_prompt = "Create a delightful story for young children"
        else:
            logger.info(f"Request ID: {request_id} - Using enriched prompt with avatar integration")
            
            system_prompt = (
                "You are a friendly and imaginative storyteller who creates elaborate, exciting, "
                "and engaging stories for children aged 3 to 5 years. "
                "Use simple words that a 3-5 year old can understand. "
                "Keep sentences short and clear but create an exciting narrative arc. "
                "Include characters that go on adventures, face challenges, and discover wonderful things. "
                "If the story is based on a concept (like kindness, sharing, or friendship), "
                "weave it into an exciting adventure story, not like a lesson. "
                "Make the story fun and interesting, with animals, toys, magical creatures, or fantasy elements. "
                "Add gentle humor, surprises, and exciting moments to keep children engaged throughout. "
                "The story should be approximately 200-250 words and feel like an exciting adventure "
                "meant to be read aloud to young children. "
                "Include multiple scenes and story progression with clear beginning, middle, and end. "
                "Always end the story with 'The End! (Created By - MyStoryBuddy)' on a new line. "
                "Format your response exactly like this:\n"
                "Title: [Your Title]\n\n"
                "[Story content with multiple paragraphs]\n\n"
                "The End! (Created By - MyStoryBuddy)\n\n"
                "Use double line breaks between paragraphs. Create 8-12 paragraphs to tell the full adventure."
            )
            user_prompt = enriched_prompt

        # Generate story with OpenAI
        logger.info(f"Request ID: {request_id} - Generating story with GPT-4o...")
        story_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        content = story_response.choices[0].message.content
        logger.info(f"Request ID: {request_id} - Story generated successfully")
        
        # Parse story response
        parts = content.split('\n\n', 1)
        if len(parts) == 2:
            title = parts[0].replace('Title:', '').strip()
            story = parts[1].strip()
        else:
            logger.warning(f"Request ID: {request_id} - Unexpected story format, using fallback")
            title = "A Magical Story"
            story = content.strip()
        
        # Ensure MyStoryBuddy branding is always present
        if "(Created By - MyStoryBuddy)" not in story:
            if story.endswith("The End!"):
                story = story[:-8].strip()
            elif "The End!" in story:
                story = story.replace("The End!", "").strip()
            story += "\n\nThe End! (Created By - MyStoryBuddy)"
        
        logger.info(f"Request ID: {request_id} - Title: {title}")

        # Generate images if Comic Book format is requested
        image_urls = []
        if "Comic Book" in formats:
            logger.info(f"Request ID: {request_id} - Generating 4 comic images...")
            image_urls = await generate_story_images(story, title, request_id, enriched_prompt)
            logger.info(f"Request ID: {request_id} - Images generated successfully")
        
        # Update story in database
        from core.database import update_story_content
        success = await update_story_content(story_id, title, story, image_urls, status='NEW')
        
        if success:
            logger.info(f"Request ID: {request_id} - Story {story_id} completed successfully")
        else:
            logger.error(f"Request ID: {request_id} - Failed to update story {story_id}")
            
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Background task failed for story_id: {story_id}")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Mark story as failed or keep as IN_PROGRESS for retry
        try:
            from core.database import update_story_content
            await update_story_content(story_id, "Story Generation Failed", 
                                     "We encountered an error while generating your story. Please try again.", 
                                     [], status='NEW')
        except Exception as db_error:
            logger.error(f"Failed to update story status after error: {str(db_error)}")

# Cache to prevent duplicate story requests
recent_requests = {}

# Routes
@app.post("/generateStory", response_model=AsyncStoryResponse)
async def generate_story_async(request: StoryRequest, req: Request, background_tasks: BackgroundTasks):
    request_id = str(uuid.uuid4())
    
    # Get current user if authenticated (optional)
    current_user = None
    try:
        current_user = await get_optional_user(req)
    except Exception as e:
        logger.warning(f"Could not get user context: {e}")
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting async story generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # Check for duplicate requests (same user + prompt within 10 seconds)
        user_id = current_user["id"] if current_user else None
        request_key = f"{user_id}:{request.prompt.strip()}"
        current_time = time.time()
        
        global recent_requests
        if request_key in recent_requests:
            time_diff = current_time - recent_requests[request_key]
            if time_diff < 10:  # 10 seconds cooldown
                logger.warning(f"Request ID: {request_id} - Duplicate request detected, ignoring")
                raise HTTPException(
                    status_code=429, 
                    detail="Please wait a moment before generating another story with the same prompt"
                )
        
        recent_requests[request_key] = current_time
        
        # Clean up old entries (older than 1 hour)
        cutoff_time = current_time - 3600
        keys_to_remove = [k for k, v in recent_requests.items() if v <= cutoff_time]
        for key in keys_to_remove:
            del recent_requests[key]
        
        # Create story placeholder in database
        from core.database import create_story_placeholder
        user_id = current_user["id"] if current_user else None
        story_id = await create_story_placeholder(
            prompt=request.prompt,
            formats=request.formats,
            request_id=request_id,
            user_id=user_id
        )
        
        if not story_id:
            raise Exception("Failed to create story placeholder")
        
        logger.info(f"Request ID: {request_id} - Created story placeholder with ID: {story_id}")
        
        # Start background task for story generation
        background_tasks.add_task(
            generate_story_background_task,
            story_id=story_id,
            prompt=request.prompt,
            formats=request.formats,
            request_id=request_id,
            user_id=user_id
        )
        
        logger.info(f"Request ID: {request_id} - Background task started for story generation")
        
        response_data = {
            "story_id": story_id,
            "status": "IN_PROGRESS",
            "message": "Story generation started! Check My Stories for updates."
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(str(e))

@app.get("/story/{story_id}/status", response_model=StoryStatusResponse)
async def get_story_status(story_id: int, req: Request):
    """Get the status of a story by its ID."""
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Request ID: {request_id} - Getting status for story_id: {story_id}")
        
        from core.database import get_story_by_id
        story = await get_story_by_id(story_id)
        
        if not story:
            return JSONResponse(
                status_code=404,
                content={"detail": "Story not found"},
                headers={
                    "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        response_data = {
            "story_id": story["id"],
            "status": story["status"],
            "title": story["title"],
            "story": story["story_content"],
            "image_urls": story["image_urls"] or [],
            "created_at": story["created_at"].isoformat() if story["created_at"] else "",
            "updated_at": story["updated_at"].isoformat() if story["updated_at"] else ""
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(str(e))

@app.put("/story/{story_id}/viewed")
async def mark_story_viewed(story_id: int, req: Request):
    """Mark a story as viewed."""
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Request ID: {request_id} - Marking story_id: {story_id} as viewed")
        
        from core.database import update_story_status
        success = await update_story_status(story_id, 'VIEWED')
        
        if not success:
            return JSONResponse(
                status_code=404,
                content={"detail": "Story not found"},
                headers={
                    "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        return JSONResponse(
            content={"message": "Story marked as viewed"},
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "PUT, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(str(e))

@app.post("/generateFunFacts", response_model=FunFactsResponse)
async def generate_fun_facts(request: FunFactRequest, req: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Get current user if authenticated (optional)
    current_user = None
    try:
        current_user = await get_optional_user(req)
    except Exception as e:
        logger.warning(f"Could not get user context: {e}")
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting fun facts generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # Create context-based fun facts prompt
        if request.prompt.strip():
            context_prompt = f"Create 10 fun facts related to the theme or characters from this story idea: '{request.prompt}'"
        else:
            context_prompt = "Create 10 fun facts about animals, nature, friendship, and adventures that would interest children"
        
        system_prompt = (
            "You are a friendly educator who creates fascinating fun facts for children aged 3-5. "
            "Generate exactly 10 fun facts in question-answer format. "
            "Each fact should be: "
            "- Simple and easy to understand for young children "
            "- Educational but entertaining "
            "- Related to the given context when possible "
            "- Formatted as a question followed by a simple answer "
            "- Keep questions starting with 'Did you know...' "
            "- Keep answers friendly, short, and exciting "
            
            "Format your response as exactly 10 Q&A pairs like this: "
            "Q: Did you know cats can sleep for 16 hours a day? "
            "A: Yes! Cats love to nap and dream just like us. "
            
            "Q: Did you know butterflies taste with their feet? "
            "A: Amazing! They step on flowers to see if they taste good. "
            
            "Make each fact delightful and wonder-filled for curious young minds."
        )
        
        logger.info(f"Request ID: {request_id} - Generating fun facts with GPT-4o...")
        fun_facts_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt}
            ],
            max_tokens=800,
            temperature=0.8
        )
        
        content = fun_facts_response.choices[0].message.content
        generation_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Fun facts generated successfully in {generation_time:.2f} seconds")
        
        # Parse the Q&A pairs
        facts = []
        lines = content.strip().split('\n')
        current_question = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('Q:'):
                current_question = line[2:].strip()
            elif line.startswith('A:') and current_question:
                answer = line[2:].strip()
                facts.append(FunFact(question=current_question, answer=answer))
                current_question = ""
        
        # Ensure we have exactly 10 facts, pad if needed
        while len(facts) < 10:
            facts.append(FunFact(
                question="Did you know reading stories helps your imagination grow?",
                answer="Yes! Every story takes you on a magical adventure in your mind."
            ))
        
        # Limit to 10 facts
        facts = facts[:10]
        
        logger.info(f"Request ID: {request_id} - Parsed {len(facts)} fun facts successfully")
        
        # Save fun facts to database (if available)
        if current_user and db_manager:
            try:
                from core.database import save_fun_facts
                facts_data = [{"question": fact.question, "answer": fact.answer} for fact in facts]
                fun_facts_id = await save_fun_facts(
                    prompt=request.prompt,
                    facts=facts_data,
                    request_id=request_id
                )
                logger.info(f"Request ID: {request_id} - Fun facts saved to database with ID: {fun_facts_id}")
            except Exception as e:
                logger.error(f"Request ID: {request_id} - Failed to save fun facts to database: {str(e)}")
                # Don't fail the request if database save fails
        
        return JSONResponse(
            content={"facts": [{"question": fact.question, "answer": fact.answer} for fact in facts]},
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(str(e))

@app.options("/generateStory")
async def preflight_generateStory():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.options("/generateFunFacts")
async def preflight_generateFunFacts():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.get("/my-stories")
async def get_user_stories(req: Request):
    """Get all stories created by the current user."""
    try:
        # Get current user using manual header parsing
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get user from database
        from auth.auth_models import UserDatabase
        current_user = await UserDatabase.get_user_by_id(user_id)
        if current_user is None:
            return JSONResponse(
                content={"error": "User not found"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        from core.database import get_stories_with_status, get_new_stories_count
        stories = await get_stories_with_status(user_id=str(current_user["id"]), limit=50)
        new_stories_count = await get_new_stories_count(user_id=str(current_user["id"]))
        
        # Format the response
        formatted_stories = []
        for story in stories:
            formatted_stories.append({
                "id": story["id"],
                "title": story["title"],
                "story_content": story["story_content"],
                "prompt": story["prompt"],
                "image_urls": story["image_urls"] or [],
                "formats": story["formats"] or [],
                "created_at": story["created_at"].isoformat() if story["created_at"] else None,
                "updated_at": story["updated_at"].isoformat() if story["updated_at"] else None,
                "status": story["status"]
            })
        
        return JSONResponse(
            content={
                "stories": formatted_stories,
                "new_stories_count": new_stories_count
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching user stories: {str(e)}")
        return JSONResponse(
            content={"error": "Failed to fetch stories"},
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )

@app.options("/my-stories")
async def preflight_my_stories():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

async def create_comic_avatar_and_extract_traits(uploaded_image_bytes: bytes, avatar_name: str, traits_description: str, request_id: str) -> tuple[bytes, str]:
    """Process uploaded image into comic-style avatar and extract visual traits from the processed version."""
    try:
        logger.info(f"Request ID: {request_id} - Starting comic avatar creation and visual traits extraction")
        
        # Add validation to ensure image bytes exist
        logger.info(f"Request ID: {request_id} - Image bytes type: {type(uploaded_image_bytes)}")
        logger.info(f"Request ID: {request_id} - Image bytes length: {len(uploaded_image_bytes) if uploaded_image_bytes else 'None'}")
        
        if not uploaded_image_bytes:
            raise HTTPException(status_code=400, detail="No image data provided")
        
        # Encode the uploaded image to base64 for GPT-4 Vision
        import base64
        try:
            image_base64 = base64.b64encode(uploaded_image_bytes).decode('utf-8')
            logger.info(f"Request ID: {request_id} - Successfully encoded image to base64")
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Error encoding image to base64: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to encode image: {str(e)}")
        
        # Step 1: Analyze uploaded image to create detailed character description
        logger.info(f"Request ID: {request_id} - Analyzing uploaded image to create character description...")
        
        description_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a character designer who creates detailed descriptions for comic book characters based on reference photos. Focus on distinctive features that would make the character recognizable in cartoon/comic form."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this image and create a detailed description for a comic book character named '{avatar_name}' with personality: {traits_description}. Focus on distinctive facial features, hair style, clothing, and any unique characteristics that would make this character recognizable when drawn in cartoon/comic style. Be specific about colors, shapes, and proportions."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        character_description = description_response.choices[0].message.content
        logger.info(f"Request ID: {request_id} - Character description created")
        
        # Step 2: Generate comic-style avatar based on the character description
        logger.info(f"Request ID: {request_id} - Creating comic-style avatar from character description...")
        
        style_prompt = f"""
Create a cute comic book/cartoon character avatar for a children's story app based on this description:

{character_description}

CHARACTER NAME: {avatar_name}
PERSONALITY: {traits_description}

STYLE REQUIREMENTS:
- Cute comic book/cartoon style (similar to Pixar/Disney animation)
- Vibrant, child-friendly colors with soft pastels
- Bold, clean outlines and smooth shapes
- Friendly, approachable appearance suitable for children aged 3-5
- Single character portrait with simple, clean background
- Make it look heroic, kind, and adventure-ready
- Suitable for children's story illustrations
- Maintain the key features described above to keep character recognizable

Transform the described features into a delightful animated character that children would love to see in their stories.
"""
        
        # Generate comic-style avatar using DALL-E
        avatar_response = await client.images.generate(
            model="gpt-image-1",
            prompt=style_prompt,
            n=1
        )
        
        # Get the generated comic avatar
        avatar_base64 = avatar_response.data[0].b64_json
        if not avatar_base64:
            raise HTTPException(status_code=500, detail="OpenAI did not return avatar image data")
            
        import base64
        comic_avatar_bytes = base64.b64decode(avatar_base64)
        logger.info(f"Request ID: {request_id} - Comic-style avatar created successfully")
        
        # Step 2: Extract visual traits from the processed comic-style avatar
        logger.info(f"Request ID: {request_id} - Extracting visual traits from comic-style avatar...")
        
        # Encode the comic avatar for analysis
        comic_avatar_base64 = base64.b64encode(comic_avatar_bytes).decode('utf-8')
        
        # Extract visual traits using the exact same approach as the working test script
        traits_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a concept artist creating character designs for comic books. Analyze artwork and create character specifications."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe the visual elements in this image as if creating a character design specification for a comic book character. Focus on artistic details like facial structure, hair style, clothing, and distinctive features."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{comic_avatar_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800,
            temperature=0.1
        )
        
        visual_traits = traits_response.choices[0].message.content
        logger.info(f"Request ID: {request_id} - Visual traits extracted successfully from comic-style avatar")
        
        return comic_avatar_bytes, visual_traits
        
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error creating comic avatar and extracting traits: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create comic avatar and extract traits: {str(e)}"
        )

async def generate_avatar_background_task(avatar_id: int, image_bytes: bytes, avatar_name: str, traits_description: str, request_id: str, user_id: int):
    """Background task to generate avatar and update status."""
    try:
        logger.info(f"Request ID: {request_id} - Starting background avatar generation for avatar_id: {avatar_id}")
        
        # Create comic-style avatar and extract visual traits
        avatar_image_bytes, visual_traits = await create_comic_avatar_and_extract_traits(
            image_bytes, avatar_name, traits_description, request_id
        )
        
        # Save avatar image to S3
        avatar_s3_url = await save_avatar_to_s3(avatar_image_bytes, user_id, request_id)
        
        # Update avatar status to completed with S3 URL and visual traits
        from core.database import update_avatar_status_with_traits
        await update_avatar_status_with_traits(avatar_id, "COMPLETED", avatar_s3_url, visual_traits)
        
        logger.info(f"Request ID: {request_id} - Avatar generation completed successfully for avatar_id: {avatar_id}")
        
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error in background avatar generation: {str(e)}")
        # Update avatar status to failed
        try:
            from core.database import update_avatar_status
            await update_avatar_status(avatar_id, "FAILED")
        except Exception as update_e:
            logger.error(f"Request ID: {request_id} - Failed to update avatar status to FAILED: {str(update_e)}")

@app.post("/personalization/avatar")
async def create_avatar(
    req: Request,
    avatar_name: str = Form(...),
    traits_description: str = Form(...),
    image: UploadFile = File(...)
):
    """Upload an image and generate a comic-style avatar for the authenticated user."""
    request_id = str(uuid.uuid4())
    
    try:
        # Get current authenticated user using manual header parsing
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get user from database
        from auth.auth_models import UserDatabase
        current_user = await UserDatabase.get_user_by_id(user_id)
        if current_user is None:
            return JSONResponse(
                content={"error": "User not found"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = current_user["id"]
        
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Creating avatar for user_id: {user_id}")
        logger.info(f"Request ID: {request_id} - Avatar name: {avatar_name}")
        logger.info(f"Request ID: {request_id} - Traits: {traits_description}")
        
        # Check if image parameter was received
        if image is None:
            logger.error(f"Request ID: {request_id} - Image parameter is None")
            raise HTTPException(status_code=400, detail="No image file provided")
        
        # Log image details for debugging
        logger.info(f"Request ID: {request_id} - Image object: {image}")
        logger.info(f"Request ID: {request_id} - Image filename: {getattr(image, 'filename', 'No filename')}")
        logger.info(f"Request ID: {request_id} - Image content_type: {getattr(image, 'content_type', 'No content_type')}")
        logger.info(f"Request ID: {request_id} - Image size: {getattr(image, 'size', 'No size')}")
        
        # Validate image file
        if not hasattr(image, 'content_type') or not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Check file size (max 10MB)
        image_bytes = await image.read()
        logger.info(f"Request ID: {request_id} - Image bytes read: {len(image_bytes) if image_bytes else 0} bytes")
        
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Image file is empty or corrupted")
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="Image file too large (max 10MB)")
        
        logger.info(f"Request ID: {request_id} - Image validation passed: {len(image_bytes)} bytes")
        
        # Create comic-style avatar and extract visual traits
        avatar_image_bytes, visual_traits = await create_comic_avatar_and_extract_traits(
            image_bytes, avatar_name, traits_description, request_id
        )
        
        # Save avatar image to S3 with special path for avatars
        avatar_s3_url = await save_avatar_to_s3(avatar_image_bytes, user_id, request_id)
        
        # Save avatar to database with extracted visual traits
        from core.database import create_user_avatar
        avatar_id = await create_user_avatar(
            user_id=user_id,
            avatar_name=avatar_name,
            traits_description=traits_description,
            s3_image_url=avatar_s3_url,
            visual_traits=visual_traits
        )
        
        # Get the created avatar for response
        from core.database import get_user_avatar
        avatar_data = await get_user_avatar(user_id)
        
        if not avatar_data:
            raise HTTPException(status_code=500, detail="Failed to retrieve created avatar")
        
        response_data = {
            "id": avatar_data["id"],
            "avatar_name": avatar_data["avatar_name"],
            "traits_description": avatar_data["traits_description"],
            "s3_image_url": avatar_data["s3_image_url"],
            "created_at": avatar_data["created_at"].isoformat(),
            "updated_at": avatar_data["updated_at"].isoformat()
        }
        
        logger.info(f"Request ID: {request_id} - Avatar created successfully with ID: {avatar_id}")
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(f"Failed to create avatar: {str(e)}")

async def save_avatar_to_s3(image_bytes: bytes, user_id: int, request_id: str) -> str:
    """Save avatar image to S3 in the avatars directory."""
    if s3_client is None:
        logger.warning(f"Request ID: {request_id} - S3 client not initialized, skipping avatar upload")
        raise HTTPException(status_code=500, detail="Image storage not available")
        
    try:
        start_time = time.time()
        logger.info(f"Request ID: {request_id} - Starting avatar S3 upload")
        
        # Use avatars directory with user_id for organization
        object_key = f"avatars/user_{user_id}_{request_id}.png"
        logger.info(f"Request ID: {request_id} - Generated object key: {object_key}")
        
        await asyncio.to_thread(
            s3_client.put_object,
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/png"
        )
        
        # Use direct S3 URL since bucket is publicly readable
        image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{object_key}"
        
        upload_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Avatar saved to S3: {image_url}")
        logger.info(f"Request ID: {request_id} - S3 upload completed in {upload_time:.2f} seconds")
        return image_url
        
    except Exception as e:
        log_error(e, request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save avatar image: {str(e)}"
        )

@app.get("/personalization/avatar", response_model=AvatarResponse)
async def get_avatar(req: Request):
    """Get the current user's avatar."""
    request_id = str(uuid.uuid4())
    
    try:
        # Get current authenticated user using manual header parsing
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get user from database
        from auth.auth_models import UserDatabase
        current_user = await UserDatabase.get_user_by_id(user_id)
        if current_user is None:
            return JSONResponse(
                content={"error": "User not found"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = current_user["id"]
        
        logger.info(f"Request ID: {request_id} - Getting avatar for user_id: {user_id}")
        
        from core.database import get_user_avatar
        avatar_data = await get_user_avatar(user_id)
        
        if not avatar_data:
            return JSONResponse(
                status_code=404,
                content={"detail": "No avatar found for user"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        response_data = {
            "id": avatar_data["id"],
            "avatar_name": avatar_data["avatar_name"],
            "traits_description": avatar_data["traits_description"],
            "s3_image_url": avatar_data["s3_image_url"],
            "created_at": avatar_data["created_at"].isoformat(),
            "updated_at": avatar_data["updated_at"].isoformat()
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(f"Failed to get avatar: {str(e)}")

@app.put("/personalization/avatar")
async def update_avatar(req: Request, update_data: AvatarUpdateRequest):
    """Update avatar name and/or traits (not the image)."""
    request_id = str(uuid.uuid4())
    
    try:
        # Get current authenticated user using manual header parsing
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get user from database
        from auth.auth_models import UserDatabase
        current_user = await UserDatabase.get_user_by_id(user_id)
        if current_user is None:
            return JSONResponse(
                content={"error": "User not found"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = current_user["id"]
        
        logger.info(f"Request ID: {request_id} - Updating avatar for user_id: {user_id}")
        
        from core.database import update_user_avatar
        success = await update_user_avatar(
            user_id=user_id,
            avatar_name=update_data.avatar_name,
            traits_description=update_data.traits_description
        )
        
        if not success:
            return JSONResponse(
                status_code=404,
                content={"detail": "No avatar found for user"},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "PUT, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get updated avatar data
        from core.database import get_user_avatar
        avatar_data = await get_user_avatar(user_id)
        
        response_data = {
            "id": avatar_data["id"],
            "avatar_name": avatar_data["avatar_name"],
            "traits_description": avatar_data["traits_description"],
            "s3_image_url": avatar_data["s3_image_url"],
            "created_at": avatar_data["created_at"].isoformat(),
            "updated_at": avatar_data["updated_at"].isoformat()
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "PUT, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(f"Failed to update avatar: {str(e)}")

@app.options("/personalization/avatar")
async def preflight_avatar():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.post("/personalization/avatar/async")
async def create_avatar_async(
    req: Request,
    background_tasks: BackgroundTasks,
    avatar_name: str = Form(...),
    traits_description: str = Form(...),
    image: UploadFile = File(...)
):
    """Start async avatar generation and return immediately."""
    request_id = str(uuid.uuid4())
    
    try:
        # Get current authenticated user
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get user from database
        from auth.auth_models import UserDatabase
        current_user = await UserDatabase.get_user_by_id(user_id)
        if current_user is None:
            return JSONResponse(
                content={"error": "User not found"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = current_user["id"]
        
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting async avatar generation for user_id: {user_id}")
        logger.info(f"Request ID: {request_id} - Avatar name: {avatar_name}")
        logger.info(f"Request ID: {request_id} - Traits: {traits_description}")
        
        # Validate image file
        if image is None:
            logger.error(f"Request ID: {request_id} - Image parameter is None")
            raise HTTPException(status_code=400, detail="No image file provided")
        
        if not hasattr(image, 'content_type') or not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read and validate image
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Image file is empty or corrupted")
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="Image file too large (max 10MB)")
        
        logger.info(f"Request ID: {request_id} - Image validation passed: {len(image_bytes)} bytes")
        
        # Create avatar placeholder in database with IN_PROGRESS status
        from core.database import create_user_avatar
        try:
            avatar_id = await create_user_avatar(
                user_id=user_id,
                avatar_name=avatar_name,
                traits_description=traits_description,
                s3_image_url="",  # Will be filled when generation completes
                status="IN_PROGRESS"
            )
            
            if not avatar_id:
                logger.error(f"Request ID: {request_id} - create_user_avatar returned None for user_id: {user_id}")
                raise HTTPException(status_code=500, detail="Failed to create avatar placeholder")
                
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Database error creating avatar placeholder: {str(e)}")
            logger.error(f"Request ID: {request_id} - User ID: {user_id}, Avatar name: {avatar_name}")
            raise HTTPException(status_code=500, detail=f"Failed to create avatar placeholder: {str(e)}")
        
        # Start background task
        background_tasks.add_task(
            generate_avatar_background_task,
            avatar_id,
            image_bytes,
            avatar_name,
            traits_description,
            request_id,
            user_id
        )
        
        logger.info(f"Request ID: {request_id} - Avatar generation started in background, avatar_id: {avatar_id}")
        
        return JSONResponse(
            content={
                "avatar_id": avatar_id,
                "status": "IN_PROGRESS",
                "message": "Avatar generation started. Check back in a few minutes!"
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request_id)
        return cors_error_response(f"Failed to start avatar generation: {str(e)}")

@app.get("/personalization/avatar/status/{avatar_id}")
async def get_avatar_status(avatar_id: int, req: Request):
    """Check the status of avatar generation."""
    try:
        # Get current authenticated user
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get avatar from database
        from core.database import get_user_avatar
        avatar_data = await get_user_avatar(user_id)
        
        if not avatar_data:
            return JSONResponse(
                content={"error": "Avatar not found"},
                status_code=404,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Check if the requested avatar_id matches the user's avatar
        if avatar_data["id"] != avatar_id:
            return JSONResponse(
                content={"error": "Avatar not found"},
                status_code=404,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        response_data = {
            "avatar_id": avatar_data["id"],
            "status": avatar_data.get("status", "COMPLETED"),
            "avatar_name": avatar_data["avatar_name"],
            "traits_description": avatar_data["traits_description"],
            "s3_image_url": avatar_data.get("s3_image_url", ""),
            "created_at": avatar_data["created_at"].isoformat(),
            "updated_at": avatar_data["updated_at"].isoformat()
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting avatar status: {str(e)}")
        return cors_error_response(f"Failed to get avatar status: {str(e)}")

@app.get("/personalization/completed-count")
async def get_completed_avatars_count(req: Request):
    """Get count of completed avatars for notification badge."""
    try:
        # Get current authenticated user
        from fastapi.security.utils import get_authorization_scheme_param
        
        authorization = req.headers.get("Authorization")
        if not authorization:
            return JSONResponse(
                content={"error": "Authentication required"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return JSONResponse(
                content={"error": "Invalid authentication scheme"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Verify JWT token
        from auth.auth_utils import JWTUtils
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return JSONResponse(
                content={"error": "Invalid token"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, Options",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        user_id = payload.get("user_id")
        if user_id is None:
            return JSONResponse(
                content={"error": "Invalid token payload"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # Get completed avatars count
        from core.database import get_completed_avatars_count
        completed_count = await get_completed_avatars_count(user_id)
        
        return JSONResponse(
            content={
                "completed_avatars_count": completed_count
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting completed avatars count: {str(e)}")
        return cors_error_response(f"Failed to get completed avatars count: {str(e)}")

@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def catch_all(path: str, request: Request):
    # Handle OPTIONS preflight for any path
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
    
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
    except json.JSONDecodeError:
        prompt = ""

    # Route to appropriate function based on path
    if path == "generateFunFacts":
        return await generate_fun_facts(FunFactRequest(prompt=prompt), request)
    else:
        # Default to story generation for backward compatibility
        from fastapi import BackgroundTasks
        background_tasks = BackgroundTasks()
        return await generate_story_async(StoryRequest(prompt=prompt), request, background_tasks)

# Database cleanup endpoint
@app.post("/admin/cleanup-stories")
async def cleanup_invalid_stories_endpoint(req: Request):
    """Admin endpoint to clean up invalid stories from the database."""
    try:
        # Optional: Add admin authentication here
        # current_user = await get_current_user(req)
        # if not current_user.get("is_admin"):
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        from core.database import cleanup_invalid_stories
        result = await cleanup_invalid_stories()
        
        return JSONResponse(
            content=result,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in cleanup endpoint: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS", 
                "Access-Control-Allow-Headers": "*"
            }
        )

 