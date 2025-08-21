#!/usr/bin/env python3
"""
Simple script to copy stories from stories table to public_stories table
"""

import asyncio
import os
import sys
import json

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables
os.environ['DB_PASSWORD'] = 'mystorybuddydb123'
os.environ['DB_USER'] = 'admin'

from core.database import db_manager

async def main():
    """Copy stories from stories table to public_stories table"""
    try:
        await db_manager.initialize()
        print("Database connected successfully")
        
        # First, let's see what stories we have
        check_query = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != '' THEN 1 ELSE 0 END) as with_images,
               SUM(CASE WHEN image_urls LIKE '%mystorybuddy-assets.s3%' THEN 1 ELSE 0 END) as with_s3_images
        FROM stories 
        WHERE status = 'NEW' AND title != 'Story in Progress...'
        """
        
        stats = await db_manager.execute_query(check_query)
        print(f"Stories statistics: {stats[0]}")
        
        # Get good stories to copy
        select_query = """
        SELECT id, title, story_content, prompt, image_urls, formats, created_at
        FROM stories 
        WHERE image_urls IS NOT NULL 
          AND image_urls != '[]' 
          AND image_urls != '' 
          AND image_urls LIKE '%mystorybuddy-assets.s3%'
          AND status = 'NEW'
          AND title != 'Story in Progress...'
          AND story_content NOT LIKE '%Your story is being generated%'
          AND LENGTH(story_content) > 200
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        stories = await db_manager.execute_query(select_query)
        print(f"Found {len(stories)} stories to copy")
        
        if not stories:
            print("No suitable stories found!")
            return
        
        # Categories and tags for variety
        categories = ["Adventure", "Friendship", "Magic", "Animals", "Learning", "Fantasy", "Family", "Courage", "Discovery"]
        tag_sets = [
            ["adventure", "brave", "journey"],
            ["friendship", "kindness", "sharing"],
            ["magic", "wonder", "fantasy"],
            ["animals", "nature", "cute"],
            ["learning", "discovery", "growth"],
            ["fantasy", "magical", "imagination"],
            ["family", "love", "together"],
            ["courage", "brave", "hero"],
            ["discovery", "explore", "find"]
        ]
        
        # Insert into public_stories
        created_count = 0
        for i, story in enumerate(stories):
            try:
                # Parse JSON fields
                image_urls = json.loads(story['image_urls']) if story['image_urls'] else []
                formats = json.loads(story['formats']) if story['formats'] else ["Text Story"]
                
                # Filter valid image URLs
                valid_image_urls = [url for url in image_urls if url and 'mystorybuddy-assets.s3' in url]
                
                if not valid_image_urls:
                    print(f"Skipping '{story['title']}' - no valid S3 URLs")
                    continue
                
                category = categories[i % len(categories)]
                tags = tag_sets[i % len(tag_sets)]
                featured = i < 2  # Make first 2 featured
                
                # Insert query
                insert_query = """
                INSERT INTO public_stories (title, story_content, prompt, image_urls, formats, category, age_group, featured, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                params = (
                    story['title'],
                    story['story_content'],
                    story['prompt'],
                    json.dumps(valid_image_urls),
                    json.dumps(formats),
                    category,
                    "3-5",
                    featured,
                    json.dumps(tags)
                )
                
                await db_manager.execute_update(insert_query, params)
                print(f"✓ Created public story: {story['title']} (Category: {category}, Featured: {featured})")
                created_count += 1
                
            except Exception as e:
                print(f"✗ Error with story '{story['title']}': {str(e)}")
                continue
        
        print(f"\nSuccessfully created {created_count} public stories!")
        
        # Verify
        verify_query = "SELECT COUNT(*) as count FROM public_stories WHERE is_active = TRUE"
        result = await db_manager.execute_query(verify_query)
        total_count = result[0]['count'] if result else 0
        print(f"Total public stories in database: {total_count}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())