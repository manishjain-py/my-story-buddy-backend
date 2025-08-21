#!/usr/bin/env python3
"""
Simple script to copy stories using basic mysql connection
"""

import pymysql
import os
import json

# Database connection
def get_db_connection():
    return pymysql.connect(
        host='database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com',
        port=3306,
        user=os.getenv('DB_USER', 'admin'),
        password=os.getenv('DB_PASSWORD', 'mystorybuddydb123'),
        database=os.getenv('DB_NAME', 'mystorybuddy'),
        charset='utf8mb4'
    )

def main():
    print("Connecting to database...")
    
    # Set environment variables
    os.environ['DB_PASSWORD'] = 'mystorybuddydb123'
    os.environ['DB_USER'] = 'admin'
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("Connected successfully!")
        
        # First, check what stories we have
        cursor.execute("""
            SELECT 
                COUNT(*) as total_stories,
                SUM(CASE WHEN image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != '' THEN 1 ELSE 0 END) as stories_with_images,
                SUM(CASE WHEN image_urls LIKE '%mystorybuddy-assets.s3%' THEN 1 ELSE 0 END) as stories_with_s3_images
            FROM stories 
            WHERE status = 'NEW' AND title != 'Story in Progress...'
        """)
        
        stats = cursor.fetchone()
        print(f"Stories stats: Total={stats[0]}, With Images={stats[1]}, With S3 Images={stats[2]}")
        
        # Get stories to copy
        cursor.execute("""
            SELECT title, story_content, prompt, image_urls, formats, created_at
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
            LIMIT 8
        """)
        
        stories = cursor.fetchall()
        print(f"Found {len(stories)} stories to copy")
        
        if not stories:
            print("No suitable stories found!")
            return
        
        # Categories and tags
        categories = ["Adventure", "Friendship", "Magic", "Animals", "Learning", "Fantasy", "Family", "Courage"]
        tag_sets = [
            ["adventure", "brave", "journey"],
            ["friendship", "kindness", "sharing"],
            ["magic", "wonder", "fantasy"],
            ["animals", "nature", "cute"],
            ["learning", "discovery", "growth"],
            ["fantasy", "magical", "imagination"],
            ["family", "love", "together"],
            ["courage", "brave", "hero"]
        ]
        
        # Copy stories one by one
        copied_count = 0
        for i, story in enumerate(stories):
            try:
                title, story_content, prompt, image_urls, formats, created_at = story
                
                # Parse image URLs
                try:
                    image_list = json.loads(image_urls) if image_urls else []
                except:
                    image_list = [image_urls] if image_urls else []
                
                # Parse formats
                try:
                    format_list = json.loads(formats) if formats else ["Text Story"]
                except:
                    format_list = ["Text Story"]
                
                # Filter valid image URLs
                valid_images = [url for url in image_list if url and 'mystorybuddy-assets.s3' in str(url)]
                
                if not valid_images:
                    print(f"Skipping '{title}' - no valid S3 URLs")
                    continue
                
                category = categories[i % len(categories)]
                tags = tag_sets[i % len(tag_sets)]
                featured = 1 if i < 2 else 0  # First 2 are featured
                
                # Insert into public_stories
                insert_sql = """
                INSERT INTO public_stories (title, story_content, prompt, image_urls, formats, category, age_group, featured, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(insert_sql, (
                    title,
                    story_content,
                    prompt,
                    json.dumps(valid_images),
                    json.dumps(format_list),
                    category,
                    '3-5',
                    featured,
                    json.dumps(tags)
                ))
                
                print(f"✓ Copied: {title} (Category: {category}, Featured: {bool(featured)})")
                copied_count += 1
                
            except Exception as e:
                print(f"✗ Error copying '{title}': {str(e)}")
                continue
        
        # Commit the changes
        conn.commit()
        print(f"\nSuccessfully copied {copied_count} stories!")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM public_stories WHERE is_active = 1")
        total = cursor.fetchone()[0]
        print(f"Total public stories in database: {total}")
        
        # Show sample
        cursor.execute("""
            SELECT title, category, featured 
            FROM public_stories 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        samples = cursor.fetchall()
        print("\nSample copied stories:")
        for sample in samples:
            print(f"  - {sample[0]} ({sample[1]}) {'⭐' if sample[2] else ''}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

if __name__ == "__main__":
    main()