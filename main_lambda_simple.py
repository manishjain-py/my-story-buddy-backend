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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from mangum import Mangum
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Story Generator",
    description="API for generating stories using OpenAI",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Can't use credentials with wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Constants
S3_BUCKET = "mystorybuddy-assets"

# Initialize clients
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize S3 client
try:
    s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-west-2'))
    try:
        s3_client.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        logger.info(f"Successfully connected to AWS S3 bucket: {S3_BUCKET}")
    except Exception as e:
        logger.warning(f"Could not verify bucket access: {str(e)}")
        logger.warning("Continuing with S3 client initialization...")
except Exception as e:
    logger.warning(f"Failed to initialize S3 client: {str(e)}")
    logger.warning("S3 functionality will be disabled. Images will not be saved.")

# Models
class StoryRequest(BaseModel):
    prompt: str = ""
    formats: list[str] = ["Comic Book", "Text Story"]

class StoryResponse(BaseModel):
    title: str
    story: str
    image_urls: list[str]

class FunFactRequest(BaseModel):
    prompt: str

class FunFact(BaseModel):
    question: str
    answer: str

class FunFactsResponse(BaseModel):
    facts: list[FunFact]

# Utility functions
def log_request_details(request: Request, request_id: str):
    """Log request details for debugging"""
    logger.info(f"Request ID: {request_id}")
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    logger.info(f"Request Client: {request.client.host if request.client else 'Unknown'}")

def log_error(error: Exception, request_id: str):
    """Log error details"""
    logger.error(f"Request ID: {request_id} - Error occurred")
    logger.error(f"Error Type: {type(error).__name__}")
    logger.error(f"Error Message: {str(error)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

def cors_error_response(error_message: str, status_code: int = 500):
    """Return error response with CORS headers"""
    return JSONResponse(
        content={"error": error_message},
        status_code=status_code,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

# Image generation function (simplified version)
async def generate_story_images(story: str, title: str, request_id: str, original_prompt: str = "") -> list[str]:
    """Generate comic-style images for the story"""
    try:
        logger.info(f"Request ID: {request_id} - Generating 4 comic images...")
        
        # Simple image generation for 4 panels
        image_urls = []
        
        for i in range(4):
            try:
                logger.info(f"Request ID: {request_id} - Starting generation for image {i+1}/4...")
                
                # Create a simple prompt for each panel
                image_prompt = f"Comic book style illustration for children's story '{title}'. Panel {i+1} of 4. {original_prompt}. Bright colors, friendly characters, safe for children."
                
                image_response = await client.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    n=1,
                    size="1024x1024"
                )
                
                image_url = image_response.data[0].url
                
                # Try to upload to S3
                try:
                    # Download image
                    async with httpx.AsyncClient() as http_client:
                        img_response = await http_client.get(image_url)
                        img_response.raise_for_status()
                        image_data = img_response.content
                    
                    # Upload to S3
                    object_key = f"stories/{request_id}_image_{i+1}.png"
                    s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=object_key,
                        Body=image_data,
                        ContentType='image/png'
                    )
                    
                    # Generate presigned URL (valid for 1 year)
                    s3_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': S3_BUCKET, 'Key': object_key},
                        ExpiresIn=31536000  # 1 year
                    )
                    
                    image_urls.append(s3_url)
                    logger.info(f"Request ID: {request_id} - Image {i+1}/4 generated and saved successfully")
                    
                except Exception as s3_error:
                    logger.warning(f"Request ID: {request_id} - Failed to save image {i+1} to S3: {str(s3_error)}")
                    image_urls.append(image_url)  # Use original URL as fallback
                    
            except Exception as img_error:
                logger.error(f"Request ID: {request_id} - Error generating image {i+1}: {str(img_error)}")
                continue
        
        logger.info(f"Request ID: {request_id} - Successfully generated {len(image_urls)}/4 images")
        return image_urls
        
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Critical error in image generation: {str(e)}")
        return []

# Routes
@app.post("/generateStory", response_model=StoryResponse)
async def generate_story(request: StoryRequest, req: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting story generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # Generate story with GPT-4
        if not request.prompt or request.prompt.strip() == "":
            logger.info(f"Request ID: {request_id} - Using default prompt")
            system_prompt = (
                "You are a creative children's story writer. Create an engaging, educational, and fun story for children aged 4-8. "
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
            logger.info(f"Request ID: {request_id} - Using custom prompt")
            system_prompt = (
                "You are a creative children's story writer. Create an engaging, educational, and fun story for children aged 4-8 based on the user's request. "
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
            user_prompt = request.prompt

        logger.info(f"Request ID: {request_id} - Generating story with GPT-4...")
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.8
        )
        
        content = response.choices[0].message.content
        story_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Story generated successfully in {story_time:.2f} seconds")
        
        # Parse title and story
        lines = content.strip().split('\n')
        title = ""
        story_content = ""
        
        for i, line in enumerate(lines):
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
                story_content = '\n'.join(lines[i+1:]).strip()
                break
        
        if not title:
            title = "A Wonderful Adventure"
            story_content = content
            
        logger.info(f"Request ID: {request_id} - Title: {title}")
        
        # Generate images if Comic Book format is selected
        image_urls = []
        if "Comic Book" in request.formats:
            images_start_time = time.time()
            image_urls = await generate_story_images(story_content, title, request_id, request.prompt)
            images_time = time.time() - images_start_time
            logger.info(f"Request ID: {request_id} - Images generated in {images_time:.2f} seconds")
        
        # Log performance metrics
        total_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Story generation completed successfully in {total_time:.2f} seconds")

        return JSONResponse(
            content={
                "title": title,
                "story": story_content,
                "image_urls": image_urls
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
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
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting fun facts generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # Generate fun facts with GPT-4
        system_prompt = (
            "You are an educational content creator for children aged 4-8. "
            "Create 10 fun, interesting, and educational facts related to the given topic. "
            "Make them age-appropriate, engaging, and easy to understand. "
            "Format each fact as a question and answer pair. "
            "Use simple language that children can understand. "
            "Make the facts surprising, delightful, and spark curiosity. "
            "Format your response exactly like this:\n\n"
            "Q: Did you know [interesting question]?\n"
            "A: [Amazing answer that kids will love]\n\n"
            "Q: Did you know [another question]?\n"
            "A: [Another wonderful answer]\n\n"
            "Continue for all 10 facts. Make each fact stand alone and be complete."
        )
        
        context_prompt = f"Create 10 fun facts about: {request.prompt}"
        
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
        
        return JSONResponse(
            content={"facts": [{"question": fact.question, "answer": fact.answer} for fact in facts]},
            headers={
                "Access-Control-Allow-Origin": "*",
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
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.options("/generateFunFacts")
async def preflight_generateFunFacts():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def catch_all(path: str, request: Request):
    # Handle OPTIONS preflight for any path
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
    
    return JSONResponse(
        content={"error": "Endpoint not found"},
        status_code=404,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

# Lambda handler
handler = Mangum(app)