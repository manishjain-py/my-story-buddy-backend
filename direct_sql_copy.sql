-- Direct SQL to copy stories from stories table to public_stories table
-- Run this script directly on the MySQL database

-- First, let's see what stories we have available
SELECT 
    COUNT(*) as total_stories,
    SUM(CASE WHEN image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != '' THEN 1 ELSE 0 END) as stories_with_images,
    SUM(CASE WHEN image_urls LIKE '%mystorybuddy-assets.s3%' THEN 1 ELSE 0 END) as stories_with_s3_images
FROM stories 
WHERE status = 'NEW' AND title != 'Story in Progress...';

-- Now copy the best stories to public_stories table
INSERT INTO public_stories (title, story_content, prompt, image_urls, formats, category, age_group, featured, tags, created_at, updated_at)
SELECT 
    title,
    story_content,
    prompt,
    image_urls,
    formats,
    CASE 
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 1 THEN 'Adventure'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 2 THEN 'Friendship'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 3 THEN 'Magic'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 4 THEN 'Animals'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 5 THEN 'Learning'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 6 THEN 'Fantasy'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 7 THEN 'Family'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 8 THEN 'Courage'
        ELSE 'Discovery'
    END as category,
    '3-5' as age_group,
    CASE WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) <= 3 THEN 1 ELSE 0 END as featured,
    CASE 
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 1 THEN '["adventure", "brave", "journey"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 2 THEN '["friendship", "kindness", "sharing"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 3 THEN '["magic", "wonder", "fantasy"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 4 THEN '["animals", "nature", "cute"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 5 THEN '["learning", "discovery", "growth"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 6 THEN '["fantasy", "magical", "imagination"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 7 THEN '["family", "love", "together"]'
        WHEN ROW_NUMBER() OVER (ORDER BY created_at DESC) % 9 = 8 THEN '["courage", "brave", "hero"]'
        ELSE '["discovery", "explore", "find"]'
    END as tags,
    created_at,
    NOW() as updated_at
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
LIMIT 12;

-- Verify the copy
SELECT 
    COUNT(*) as total_public_stories,
    COUNT(CASE WHEN featured = 1 THEN 1 END) as featured_stories,
    GROUP_CONCAT(DISTINCT category) as categories
FROM public_stories 
WHERE is_active = 1;

-- Show sample of copied stories
SELECT id, title, category, featured, LENGTH(story_content) as content_length
FROM public_stories 
WHERE is_active = 1
ORDER BY created_at DESC
LIMIT 5;