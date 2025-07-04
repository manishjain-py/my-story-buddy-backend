from openai import OpenAI
import base64
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

def generate_test_image():
    prompt = """
    Create a 4-panel comic-style illustration for a children's story titled "The Lost Balloon", aimed at ages 3–5. The comic should use cute and friendly characters, a soft pastel color palette, and have a storybook-like, gentle feel. Each panel should include short captions or speech bubbles to advance the story, with a warm and whimsical tone.

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

    try:
        print("Generating image...")
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt
        )

        print("Image generated successfully!")
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        # Create test_images directory if it doesn't exist
        os.makedirs("test_images", exist_ok=True)

        # Save the image to a file
        output_path = "test_images/lost_balloon.png"
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        
        print(f"Image saved successfully to {output_path}")
        return True

    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return False

if __name__ == "__main__":
    generate_test_image() 