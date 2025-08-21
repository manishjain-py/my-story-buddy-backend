#!/usr/bin/env python3
"""
Script to populate public_stories table with sample data from existing user_stories.
This takes stories with valid S3 URLs and converts them to public stories for testing.
"""

import asyncio
import os
import sys
import logging

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.database import db_manager, create_public_story

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_sample_stories():
    """Get sample stories from user_stories table that have valid S3 URLs."""
    query = """
    SELECT title, story_content, prompt, image_urls, formats, created_at
    FROM stories 
    WHERE image_urls IS NOT NULL 
      AND image_urls != '[]' 
      AND image_urls != '' 
      AND image_urls LIKE '%s3%'
      AND status = 'NEW'
      AND title != 'Story in Progress...'
    ORDER BY created_at DESC
    LIMIT 10
    """
    
    try:
        results = await db_manager.execute_query(query)
        logger.info(f"Found {len(results)} sample stories with valid S3 URLs")
        return results
    except Exception as e:
        logger.error(f"Error fetching sample stories: {str(e)}")
        return []

async def populate_public_stories():
    """Populate public_stories table with sample data."""
    try:
        # Initialize database connection
        await db_manager.initialize()
        logger.info("Database connection initialized")
        
        # Get sample stories
        sample_stories = await get_sample_stories()
        
        if not sample_stories:
            logger.warning("No sample stories found to populate public stories")
            return
        
        # Sample categories and tags for variety
        categories = ["Adventure", "Friendship", "Magic", "Animals", "Learning", "Fantasy"]
        tag_sets = [
            ["adventure", "brave", "journey"],
            ["friendship", "kindness", "sharing"],
            ["magic", "wonder", "fantasy"],
            ["animals", "nature", "cute"],
            ["learning", "discovery", "growth"],
            ["fantasy", "magical", "imagination"]
        ]
        
        # Convert sample stories to public stories
        created_count = 0
        for i, story in enumerate(sample_stories):
            try:
                # Parse image URLs (they're stored as JSON strings)
                import json
                image_urls = json.loads(story['image_urls']) if story['image_urls'] else []
                formats = json.loads(story['formats']) if story['formats'] else ["Text Story"]
                
                # Add variety to categories and tags
                category = categories[i % len(categories)]
                tags = tag_sets[i % len(tag_sets)]
                featured = i < 3  # Make first 3 stories featured
                
                # Create public story
                public_story_id = await create_public_story(
                    title=story['title'],
                    story_content=story['story_content'],
                    prompt=story['prompt'],
                    image_urls=image_urls,
                    formats=formats,
                    category=category,
                    age_group="3-5",
                    featured=featured,
                    tags=tags
                )
                
                logger.info(f"Created public story {public_story_id}: {story['title']} (Category: {category}, Featured: {featured})")
                created_count += 1
                
            except Exception as e:
                logger.error(f"Error creating public story from '{story['title']}': {str(e)}")
                continue
        
        logger.info(f"Successfully created {created_count} public stories")
        
        # Verify the created stories
        verification_query = "SELECT COUNT(*) as count FROM public_stories WHERE is_active = TRUE"
        result = await db_manager.execute_query(verification_query)
        total_count = result[0]['count'] if result else 0
        logger.info(f"Total public stories in database: {total_count}")
        
        # Show featured stories
        featured_query = "SELECT title, category FROM public_stories WHERE featured = TRUE AND is_active = TRUE"
        featured_stories = await db_manager.execute_query(featured_query)
        logger.info(f"Featured stories: {[(s['title'], s['category']) for s in featured_stories]}")
        
    except Exception as e:
        logger.error(f"Error populating public stories: {str(e)}")
        raise
    finally:
        await db_manager.close()
        logger.info("Database connection closed")

async def clear_public_stories():
    """Clear all public stories (for testing purposes)."""
    try:
        await db_manager.initialize()
        logger.info("Clearing all public stories...")
        
        delete_query = "DELETE FROM public_stories"
        affected_rows = await db_manager.execute_update(delete_query)
        logger.info(f"Deleted {affected_rows} public stories")
        
    except Exception as e:
        logger.error(f"Error clearing public stories: {str(e)}")
        raise
    finally:
        await db_manager.close()

async def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        logger.info("Clearing public stories...")
        await clear_public_stories()
    else:
        logger.info("Populating public stories with sample data...")
        await populate_public_stories()

if __name__ == "__main__":
    asyncio.run(main())