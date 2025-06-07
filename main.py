import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from mangum import Mangum

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
    allow_origins=["*"],  # Allow all origins for now
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class StoryRequest(BaseModel):
    prompt: str

class StoryResponse(BaseModel):
    story: str

@app.post("/generateStory", response_model=StoryResponse)
async def generate_story(request: StoryRequest):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a creative storyteller who creates engaging and imaginative stories for children."},
                {"role": "user", "content": request.prompt}
            ],
            max_tokens=300,  # Reduced from 500 to improve response time
            temperature=0.7
        )
        
        story = response.choices[0].message.content
        return StoryResponse(story=story)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create handler for AWS Lambda with optimized settings
handler = Mangum(app, lifespan="off")

# Add a catch-all route to handle API Gateway stage
@app.api_route("/{path:path}", methods=["POST"])
async def catch_all(path: str):
    if path.startswith("default/"):
        path = path[8:]  # Remove "default/"
    
    if path == "generateStory":
        return await generate_story(StoryRequest(prompt="Tell me a story about a robot in space"))
    
    raise HTTPException(status_code=404, detail="Not Found") 