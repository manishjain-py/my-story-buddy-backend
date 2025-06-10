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
        # STEP 1: Generate the story using GPT-3.5-turbo
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

        story_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        content = story_response.choices[0].message.content
        
        # Split the response into title and story
        parts = content.split('\n\n', 1)
        if len(parts) == 2:
            title = parts[0].replace('Title:', '').strip()
            story = parts[1].strip()
        else:
            # Fallback if the format is not as expected
            title = "A Magical Story"
            story = content.strip()

        # STEP 2: Generate visual storytelling prompt using GPT-3.5-turbo
        visual_prompt_template = f"""
You are a visual storyteller and illustrator for children's books.

Based on the story I give you, create a prompt that can be used to generate a 4-panel comic-style illustration. The comic should be designed for children aged 3 to 5, using:
 - Cute and friendly characters (animals, nature, toys, etc.)
 - Pastel colors and a soft, storybook feel
 - Speech bubbles or short captions inside each panel to represent the story text
 - A gentle and fun tone that aligns with early childhood education
 - Visually match this style reference: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/PHOTO-2025-06-09-11-37-16.jpg

Each of the 4 panels should move the story forward, visually representing characters, scenes, and dialogue.

Here is the story you should base the comic on:

Title: {title}

{story}

------

To help you understand the expected output, here's an example:

Create a 4-panel comic-style illustration for a children's story titled "The Lost Balloon", aimed at ages 3-5. The comic should use cute and friendly characters, a soft pastel color palette, and have a storybook-like, gentle feel. Each panel should include short captions or speech bubbles to advance the story, with a warm and whimsical tone.

The visual style should match this reference: https://mystorybuddy-assets.s3.us-east-1.amazonaws.com/PHOTO-2025-06-09-11-37-16.jpg — soft outlines, dreamy lighting, and expressive characters.

⸻

Panel 1

Scene: A sunny park with a small girl (Lily) holding a red balloon.  
Action: The balloon slips from Lily's hand and begins to float up.  
Caption (inside panel): "One sunny day, a red balloon floated away from Lily's hand."

⸻

Panel 2

Scene: The balloon soaring high in the sky past trees and rooftops. A friendly bluebird spots it.  
Speech Bubble (bird): "Where are you going?"  
Speech Bubble (balloon): "I'm looking for adventure!"

⸻

Panel 3

Scene: Sunset sky with the balloon gently drifting down with a warm breeze.  
Caption (inside panel): "At sunset, the wind gently brought the balloon back…"

⸻

Panel 4

Scene: Lily hugging the balloon tightly, smiling with joy.  
Caption (inside panel): "She hugged it tight."  
A small heart above her head to show affection.

⸻

Make sure all characters have big, friendly eyes and gentle expressions. Use a soft, calming background in each frame with elements like clouds, birds, and treetops to keep the environment child-friendly and comforting.
"""
        visual_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a visual storyteller and illustrator for children's books."},
                {"role": "user", "content": visual_prompt_template}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        final_image_prompt = visual_response.choices[0].message.content

        # STEP 3: Generate image using DALL-E 3
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=final_image_prompt,
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