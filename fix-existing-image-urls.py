#!/usr/bin/env python3
"""
Script to fix existing story image URLs in the database.
Replace presigned URLs with direct S3 URLs.
"""

import asyncio
import re
from database import get_database
from auth_models import UserDatabase

async def fix_image_urls():
    """Fix existing image URLs in the database"""
    try:
        # Get database connection
        db = await get_database()
        user_db = UserDatabase(db)
        
        # Get all stories
        query = "SELECT id, image_urls FROM stories WHERE image_urls IS NOT NULL AND image_urls != ''"
        results = await db.fetch_all(query)
        
        print(f"Found {len(results)} stories with image URLs")
        
        updated_count = 0
        for row in results:
            story_id = row[0]
            current_urls = row[1]
            
            if not current_urls:
                continue
                
            # Parse the JSON array of URLs
            import json
            try:
                urls = json.loads(current_urls)
            except:
                print(f"Skipping story {story_id} - invalid JSON: {current_urls}")
                continue
            
            # Fix each URL
            new_urls = []
            changed = False
            
            for url in urls:
                if "AWSAccessKeyId=" in url and "Signature=" in url:
                    # This is a presigned URL, extract the object key and convert to direct URL
                    match = re.search(r'https://mystorybuddy-assets\.s3\.amazonaws\.com/([^?]+)', url)
                    if match:
                        object_key = match.group(1)
                        new_url = f"https://mystorybuddy-assets.s3.amazonaws.com/{object_key}"
                        new_urls.append(new_url)
                        changed = True
                        print(f"Fixed URL: {object_key}")
                    else:
                        new_urls.append(url)
                else:
                    # Already a direct URL or different format
                    new_urls.append(url)
            
            if changed:
                # Update the database
                new_urls_json = json.dumps(new_urls)
                update_query = "UPDATE stories SET image_urls = :image_urls WHERE id = :id"
                await db.execute(update_query, {"image_urls": new_urls_json, "id": story_id})
                updated_count += 1
                print(f"Updated story {story_id}")
        
        print(f"Updated {updated_count} stories with fixed image URLs")
        
    except Exception as e:
        print(f"Error fixing image URLs: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_image_urls())