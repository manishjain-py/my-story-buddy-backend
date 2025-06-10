import os
from fastapi import FastAPI, HTTPException, Request
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
    prompt: str = ""  # Make prompt optional with empty string default

class StoryResponse(BaseModel):
    title: str
    story: str
    image_url: str

@app.post("/generateStory", response_model=StoryResponse)
async def generate_story(request: StoryRequest):
    try:
        # If no prompt is provided, create a creative prompt
        if not request.prompt.strip():
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

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Split the response into title and story
        parts = content.split('\n\n', 1)
        if len(parts) == 2:
            title = parts[0].replace('Title:', '').strip()
            story = parts[1].strip()
        else:
            # Fallback if the format is not as expected
            title = "A Magical Story"
            story = content.strip()

        # Generate image prompt based on the story
        image_prompt = f"Create a child-friendly, colorful illustration for a children's story titled '{title}'. The image should be cute, simple, and suitable for young children. Use bright, cheerful colors and a simple, clear style that appeals to 3-4 year olds. The scene should be from the story: {story[:200]}..."

        # Generate image using DALL-E
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = image_response.data[0].url
        
        return StoryResponse(title=title, story=story, image_url=image_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create handler for AWS Lambda with optimized settings
handler = Mangum(app, lifespan="off")

# Add a catch-all route to handle API Gateway stage
@app.api_route("/{path:path}", methods=["POST"])
async def catch_all(path: str, request: Request):
    if path.startswith("default/"):
        path = path[8:]  # Remove "default/"
    
    if path == "generateStory":
        body = await request.json()
        return await generate_story(StoryRequest(prompt=body.get("prompt", "")))
    
    raise HTTPException(status_code=404, detail="Not Found") 