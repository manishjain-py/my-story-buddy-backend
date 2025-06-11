import os
import logging
import time
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from mangum import Mangum
import base64
import boto3
import uuid
import traceback
import httpx
import botocore

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI with minimal settings
app = FastAPI(
    title="Story Generator",
    description="API for generating stories using OpenAI",
    version="1.0.0",
    docs_url=None,  # Disable Swagger UI
    redoc_url=None  # Disable ReDoc
)

# Configure CORS with minimal settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.mystorybuddy.com", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

S3_BUCKET = "mystorybuddy-assets"  # Your S3 bucket name

# Initialize S3 client
try:
    s3_client = boto3.client('s3')
    # Test access to our specific bucket instead of listing all buckets
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

class StoryRequest(BaseModel):
    prompt: str = ""  # Make prompt optional with empty string default

class StoryResponse(BaseModel):
    title: str
    story: str
    image_url: str

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

async def save_image_to_s3(image_bytes: bytes, content_type: str = "image/png", request_id: str = None) -> str:
    """Save image bytes to S3 and return the URL."""
    if s3_client is None:
        logger.warning(f"Request ID: {request_id} - S3 client not initialized, skipping image upload")
        return "https://via.placeholder.com/400x300?text=Image+Upload+Disabled"
        
    try:
        start_time = time.time()
        logger.info(f"Request ID: {request_id} - Starting S3 upload")
        
        # Generate a unique filename
        object_key = f"stories/{uuid.uuid4()}.png"
        logger.info(f"Request ID: {request_id} - Generated object key: {object_key}")
        
        # Upload to S3 using asyncio.to_thread to avoid blocking
        await asyncio.to_thread(
            s3_client.put_object,
            Bucket=S3_BUCKET,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type
        )
        
        # Generate a pre-signed URL that expires in 1 hour
        image_url = await asyncio.to_thread(
            s3_client.generate_presigned_url,
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': object_key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        
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

@app.post("/generateStory", response_model=StoryResponse)
async def generate_story(request: StoryRequest, req: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting story generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # STEP 1: Generate the story using GPT-3.5-turbo
        story_start_time = time.time()
        if not request.prompt.strip():
            logger.info(f"Request ID: {request_id} - Using default prompt")
            system_prompt = (
                "You are a friendly and imaginative storyteller who creates short, fun, "
                "and engaging stories for children aged 3 to 4. "
                "Create a completely original and creative story that would delight young children. "
                "Use only very simple words that a 3-year-old can understand. "
                "Keep sentences short and clear. "
                "Avoid any complex words or concepts. "
                "Make the story cute and interesting, with animals, toys, or magical things. "
                "Add some gentle humor and surprises to keep children engaged. "
                "The story should be under 100 words and feel like it's meant to be read aloud to a small child. "
                "Always end the story with 'The End!' on a new line. "
                "Format your response exactly like this:\n"
                "Title: [Your Title]\n\n"
                "[First paragraph of the story]\n\n"
                "[Second paragraph of the story]\n\n"
                "[Third paragraph of the story]\n\n"
                "The End!\n\n"
                "Use double line breaks between paragraphs. Keep paragraphs short and engaging."
            )
            user_prompt = "Create a delightful story for young children"
        else:
            logger.info(f"Request ID: {request_id} - Using custom prompt")
            system_prompt = (
                "You are a friendly and imaginative storyteller who creates short, fun, "
                "and engaging stories for children aged 3 to 4. "
                "Use only very simple words that a 3-year-old can understand. "
                "Keep sentences short and clear. "
                "Avoid any complex words or concepts. "
                "If the story is based on a concept (like kindness, sharing, or brushing teeth), "
                "explain it through a fun story, not like a lesson. "
                "Make the story cute and interesting, with animals, toys, or magical things if possible. "
                "Add some gentle humor and surprises to keep children engaged. "
                "The story should be under 100 words and feel like it's meant to be read aloud to a small child. "
                "Always end the story with 'The End!' on a new line. "
                "Format your response exactly like this:\n"
                "Title: [Your Title]\n\n"
                "[First paragraph of the story]\n\n"
                "[Second paragraph of the story]\n\n"
                "[Third paragraph of the story]\n\n"
                "The End!\n\n"
                "Use double line breaks between paragraphs. Keep paragraphs short and engaging."
            )
            user_prompt = request.prompt

        logger.info(f"Request ID: {request_id} - Generating story with GPT-3.5-turbo...")
        story_response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        content = story_response.choices[0].message.content
        story_time = time.time() - story_start_time
        logger.info(f"Request ID: {request_id} - Story generated successfully in {story_time:.2f} seconds")
        
        # Split the response into title and story
        parts = content.split('\n\n', 1)
        if len(parts) == 2:
            title = parts[0].replace('Title:', '').strip()
            story = parts[1].strip()
        else:
            logger.warning(f"Request ID: {request_id} - Unexpected story format, using fallback")
            title = "A Magical Story"
            story = content.strip()
        
        logger.info(f"Request ID: {request_id} - Title: {title}")

        # STEP 2: Generate visual storytelling prompt using GPT-3.5-turbo
        visual_start_time = time.time()
        logger.info(f"Request ID: {request_id} - Generating visual prompt...")
        visual_prompt_template = f"""
Create a 4-panel comic-style illustration for a children's story titled "{title}".

Story:
{story}

Requirements:
- Use cute, friendly characters with big eyes and gentle expressions
- Soft pastel colors and storybook-like style
- Each panel should advance the story
- Include speech bubbles or short captions
- Match this style reference: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/PHOTO-2025-06-09-11-37-16.jpg

Format each panel like this:
Panel 1: [Scene description]
Panel 2: [Scene description]
Panel 3: [Scene description]
Panel 4: [Scene description]

Keep descriptions concise but include key visual elements, emotions, and actions.
"""
        visual_response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a visual storyteller for children's books. Create clear, concise panel descriptions."},
                {"role": "user", "content": visual_prompt_template}
            ],
            max_tokens=1000,  # Reduced from 4000 to stay within limits
            temperature=0.7
        )
        
        final_image_prompt = visual_response.choices[0].message.content
        visual_time = time.time() - visual_start_time
        logger.info(f"Request ID: {request_id} - Visual prompt generated successfully in {visual_time:.2f} seconds")

        # STEP 3: Generate image using GPT-Image-1
        image_start_time = time.time()
        logger.info(f"Request ID: {request_id} - Generating image with GPT-Image-1...")
        image_response = await client.images.generate(
            model="gpt-image-1",
            prompt=final_image_prompt,
            n=1
        )

        # Get the base64 image data
        image_base64 = image_response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        image_time = time.time() - image_start_time
        logger.info(f"Request ID: {request_id} - Image generated successfully in {image_time:.2f} seconds")

        # Save to S3 and get URL
        image_url = await save_image_to_s3(image_bytes, request_id=request_id)
        
        total_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Story generation completed successfully in {total_time:.2f} seconds")
        logger.info(f"Request ID: {request_id} - Performance metrics:")
        logger.info(f"  - Story generation: {story_time:.2f}s")
        logger.info(f"  - Visual prompt: {visual_time:.2f}s")
        logger.info(f"  - Image generation: {image_time:.2f}s")
        logger.info(f"  - Total time: {total_time:.2f}s")

        return StoryResponse(title=title, story=story, image_url=image_url)
        
    except Exception as e:
        log_error(e, request_id)
        raise HTTPException(status_code=500, detail=str(e))

# Create handler for AWS Lambda with optimized settings
handler = Mangum(app, lifespan="off")

# Add a catch-all route to handle API Gateway stage
@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def catch_all(path: str, request: Request):
    request_id = str(uuid.uuid4())
    log_request_details(request, request_id)
    
    # Handle OPTIONS request for CORS preflight
    if request.method == "OPTIONS":
        logger.info(f"Request ID: {request_id} - Handling OPTIONS request")
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Accept",
                "Access-Control-Max-Age": "86400"  # 24 hours
            },
            "body": ""
        }

    if path.startswith("default/"):
        path = path[8:]  # Remove "default/"
        logger.info(f"Request ID: {request_id} - Removed 'default/' prefix from path")
    
    if path == "generateStory":
        logger.info(f"Request ID: {request_id} - Processing generateStory request")
        body = await request.json()
        return await generate_story(StoryRequest(prompt=body.get("prompt", "")), request)
    
    logger.warning(f"Request ID: {request_id} - Path not found: {path}")
    raise HTTPException(status_code=404, detail="Not Found") 