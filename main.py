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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.mystorybuddy.com", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
    logger.warning("To enable S3 functionality, ensure AWS credentials have proper permissions:")
    logger.warning("1. AWS CLI: aws configure")
    logger.warning("2. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    logger.warning("3. AWS credentials file: ~/.aws/credentials")
    logger.warning(f"4. Required permissions: s3:PutObject, s3:GetObject on bucket: {S3_BUCKET}")

# Models
class StoryRequest(BaseModel):
    prompt: str = ""

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
        
        image_url = await asyncio.to_thread(
            s3_client.generate_presigned_url,
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': object_key
            },
            ExpiresIn=3600
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

async def generate_story_images(story: str, title: str, request_id: str, original_prompt: str = "") -> list[str]:
    """Generate one unified comic image and split it into 4 separate panels for perfect consistency."""
    image_urls = []
    
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
        model="gpt-4.1",
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
    
    image_titles = [
        f"{title} - Part 1: The Beginning",
        f"{title} - Part 2: The Adventure",
        f"{title} - Part 3: The Challenge", 
        f"{title} - Part 4: The Resolution"
    ]
    
    # Check for personalized characters
    personalization_note = ""
    if "aadyu" in original_prompt.lower() or "aadyu" in story.lower():
        personalization_note = f'''

IMPORTANT PERSONALIZATION: Include Aadyu as a main character in this comic.
Aadyu should be depicted as a young boy who is funny, creative, and very smart.
Reference this character design: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/personalised/aadyu.PNG
Make Aadyu a central figure in the panels, showing his personality through expressions and actions.
'''

    # Create the unified 4-panel comic prompt
    logger.info(f"Request ID: {request_id} - Generating unified 4-panel comic...")
    unified_start_time = time.time()
    
    # Format story parts for the prompt
    story_parts_text = ""
    for i, (story_part, image_title) in enumerate(zip(story_parts, image_titles)):
        story_parts_text += f"\nPanel {i+1} - {image_title.split(' - ', 1)[1]}:\n{story_part}\n"
    
    unified_visual_prompt = f'''
Create a single comic page with 4 quadrants arranged in a 2x2 grid for "{title}".

STORY BREAKDOWN:
{story_parts_text}

OVERALL LAYOUT REQUIREMENTS:
- Create a 2x2 grid of quadrants: 
  [Quadrant 1: Part 1] [Quadrant 2: Part 2]
  [Quadrant 3: Part 3] [Quadrant 4: Part 4]
- Each quadrant should be the same size and clearly separated by thick black borders
- The overall image should be square or slightly rectangular
- Each quadrant contains a complete 4-panel comic for that story part

QUADRANT LAYOUT (within each quadrant):
Each quadrant should contain exactly 4 panels in a 2x2 arrangement:
[Panel 1] [Panel 2]
[Panel 3] [Panel 4]

VISUAL STYLE:
- Use cute, friendly characters with big eyes and gentle expressions
- Use soft pastel colors and a storybook-like visual style
- Keep the tone gentle, magical, and fun
- Maintain perfect character consistency across ALL quadrants and panels
- Match this visual style: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/PHOTO-2025-06-09-11-37-16.jpg{personalization_note}

QUADRANT CONTENT:
Quadrant 1 (Top-Left): {story_parts[0]} (Setup and introduction) - Show this story part across 4 panels
Quadrant 2 (Top-Right): {story_parts[1]} (Development and adventure) - Show this story part across 4 panels
Quadrant 3 (Bottom-Left): {story_parts[2]} (Challenge or climax) - Show this story part across 4 panels
Quadrant 4 (Bottom-Right): {story_parts[3]} (Resolution and conclusion) - Show this story part across 4 panels

TECHNICAL REQUIREMENTS:
- Each quadrant tells one complete story part across its 4 panels
- Include speech bubbles or captions where appropriate
- Ensure smooth visual flow within each quadrant and between quadrants
- Characters must look identical across all quadrants and panels
- Clear black borders between quadrants for easy splitting
- Suitable for children aged 3-5

Create this as a single 2x2 grid image that can be split into 4 individual comic pages.
'''

    try:
        # Generate the unified comic image
        logger.info(f"Request ID: {request_id} - Calling GPT-Image-1 for unified comic generation...")
        image_response = await client.images.generate(
            model="gpt-image-1",
            prompt=unified_visual_prompt,
            n=1
        )
        
        image_base64 = image_response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        unified_time = time.time() - unified_start_time
        
        logger.info(f"Request ID: {request_id} - Unified comic generated in {unified_time:.2f} seconds")
        
        # Process and split the image
        logger.info(f"Request ID: {request_id} - Processing and splitting unified comic into 4 panels...")
        split_start_time = time.time()
        
        # Load the image using PIL
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size
        
        # Calculate quadrant dimensions (split into 2x2 grid)
        quadrant_width = width // 2
        quadrant_height = height // 2
        
        # Define quadrant positions in order: Q1 (top-left), Q2 (top-right), Q3 (bottom-left), Q4 (bottom-right)
        quadrant_positions = [
            (0, 0),                                        # Q1: Top-left
            (quadrant_width, 0),                          # Q2: Top-right  
            (0, quadrant_height),                         # Q3: Bottom-left
            (quadrant_width, quadrant_height)             # Q4: Bottom-right
        ]
        
        # Split into 4 quadrants
        for i, (left, top) in enumerate(quadrant_positions):
            right = left + quadrant_width
            bottom = top + quadrant_height
            
            # Crop the quadrant
            quadrant = image.crop((left, top, right, bottom))
            
            # Convert quadrant back to bytes
            quadrant_buffer = BytesIO()
            quadrant.save(quadrant_buffer, format='PNG')
            quadrant_bytes = quadrant_buffer.getvalue()
            
            # Save to S3
            quadrant_url = await save_image_to_s3(quadrant_bytes, request_id=request_id, image_index=i+1)
            image_urls.append(quadrant_url)
            
            logger.info(f"Request ID: {request_id} - Quadrant {i+1}/4 (Story Part {i+1}) processed and saved successfully")
        
        split_time = time.time() - split_start_time
        logger.info(f"Request ID: {request_id} - Image splitting completed in {split_time:.2f} seconds")
        logger.info(f"Request ID: {request_id} - Total unified comic process: {unified_time + split_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error generating unified comic: {str(e)}")
        # Fallback to placeholder images
        for i in range(4):
            image_urls.append("https://via.placeholder.com/400x300?text=Comic+Generation+Failed")
    
    return image_urls

# Routes
@app.post("/generateStory", response_model=StoryResponse)
async def generate_story(request: StoryRequest, req: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        log_request_details(req, request_id)
        logger.info(f"Request ID: {request_id} - Starting story generation")
        logger.info(f"Request ID: {request_id} - Prompt: {request.prompt[:100]}...")
        
        # Generate story
        story_start_time = time.time()
        if not request.prompt.strip():
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
            logger.info(f"Request ID: {request_id} - Using custom prompt")
            
            # Check for personalized characters
            personalized_prompt = ""
            original_prompt = request.prompt.lower()
            
            if "aadyu" in original_prompt:
                logger.info(f"Request ID: {request_id} - Detected personalized character: Aadyu")
                personalized_prompt = (
                    "\n\nIMPORTANT PERSONALIZATION: This story includes Aadyu, a special character. "
                    "Aadyu is a funny, creative, and very smart boy who loves adventures. "
                    "Make sure to include him as a main character in the story with these personality traits. "
                    "Show his humor through clever jokes or funny situations, his creativity through "
                    "unique problem-solving or imaginative ideas, and his intelligence through smart "
                    "observations or helpful solutions to challenges in the story."
                )
            
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
                + personalized_prompt
            )
            user_prompt = request.prompt

        logger.info(f"Request ID: {request_id} - Generating story with GPT-4.1...")
        story_response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        content = story_response.choices[0].message.content
        story_time = time.time() - story_start_time
        logger.info(f"Request ID: {request_id} - Story generated successfully in {story_time:.2f} seconds")
        
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
            # Remove any existing "The End!" and add our branded version
            if story.endswith("The End!"):
                story = story[:-8].strip()  # Remove "The End!"
            elif "The End!" in story:
                story = story.replace("The End!", "").strip()
            
            # Add our branded ending
            story += "\n\nThe End! (Created By - MyStoryBuddy)"
        
        logger.info(f"Request ID: {request_id} - Title: {title}")

        # Generate multiple images
        images_start_time = time.time()
        logger.info(f"Request ID: {request_id} - Generating 4 comic images...")
        image_urls = await generate_story_images(story, title, request_id, request.prompt)
        images_time = time.time() - images_start_time
        logger.info(f"Request ID: {request_id} - All 4 images generated successfully in {images_time:.2f} seconds")
        
        # Log performance metrics
        total_time = time.time() - start_time
        logger.info(f"Request ID: {request_id} - Story generation completed successfully in {total_time:.2f} seconds")
        logger.info(f"Request ID: {request_id} - Performance metrics:")
        logger.info(f"  - Story generation: {story_time:.2f}s")
        logger.info(f"  - Images generation: {images_time:.2f}s")
        logger.info(f"  - Total time: {total_time:.2f}s")

        return JSONResponse(
            content={
                "title": title,
                "story": story,
                "image_urls": image_urls
            },
            headers={
                "Access-Control-Allow-Origin": "https://www.mystorybuddy.com",
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
        
        logger.info(f"Request ID: {request_id} - Generating fun facts with GPT-4.1...")
        fun_facts_response = await client.chat.completions.create(
            model="gpt-4.1",
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
        return await generate_story(StoryRequest(prompt=prompt), request)

# Create handler for AWS Lambda
handler = Mangum(app) 