#!/usr/bin/env python3
"""
Database connectivity test script for My Story Buddy
"""
import asyncio
import logging
import os
from database import db_manager, create_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_database_connectivity():
    """Test database connectivity and setup."""
    try:
        print("=" * 60)
        print("MY STORY BUDDY - DATABASE CONNECTIVITY TEST")
        print("=" * 60)
        
        # Check environment variables
        print("\n1. Checking environment variables...")
        db_user = os.getenv('DB_USER', 'admin')
        db_password = os.getenv('DB_PASSWORD')
        db_name = os.getenv('DB_NAME', 'mystorybuddy')
        
        print(f"   DB_USER: {db_user}")
        print(f"   DB_PASSWORD: {'***SET***' if db_password else '***NOT SET***'}")
        print(f"   DB_NAME: {db_name}")
        
        if not db_password:
            print("\n❌ ERROR: DB_PASSWORD environment variable not set!")
            print("Please set it using: export DB_PASSWORD='your_password'")
            return False
            
        print("   ✅ Environment variables configured")
        
        # Test database connection
        print("\n2. Testing database connection...")
        await db_manager.initialize()
        
        if not db_manager.pool:
            print("   ❌ Failed to initialize database connection")
            return False
            
        print("   ✅ Database connection successful!")
        
        # Test basic query
        print("\n3. Testing basic database query...")
        result = await db_manager.execute_query("SELECT NOW() as `current_time`, DATABASE() as `current_db`")
        if result:
            print(f"   ✅ Query successful!")
            print(f"   Current time: {result[0]['current_time']}")
            print(f"   Current database: {result[0]['current_db']}")
        else:
            print("   ❌ Query failed")
            return False
            
        # Create tables
        print("\n4. Creating/verifying database tables...")
        await create_tables()
        print("   ✅ Tables created/verified successfully!")
        
        # Test table access
        print("\n5. Testing table access...")
        tables = await db_manager.execute_query("SHOW TABLES")
        print(f"   Available tables: {[table[list(table.keys())[0]] for table in tables]}")
        
        # Test insert and select
        print("\n6. Testing data operations...")
        
        # Test story insert
        from database import save_story
        story_id = await save_story(
            title="Test Story",
            story_content="This is a test story content.",
            prompt="test prompt",
            image_urls=["http://example.com/image1.jpg"],
            formats=["Text Story"],
            request_id="test-123",
            user_id="test-user"
        )
        print(f"   ✅ Test story saved with ID: {story_id}")
        
        # Test story retrieval
        from database import get_recent_stories
        stories = await get_recent_stories(limit=1)
        if stories:
            print(f"   ✅ Retrieved {len(stories)} story(s)")
            print(f"   Latest story: {stories[0]['title']}")
        else:
            print("   ⚠️  No stories found")
            
        print("\n" + "=" * 60)
        print("✅ DATABASE CONNECTIVITY TEST COMPLETED SUCCESSFULLY!")
        print("✅ Your database is ready for My Story Buddy!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: Database test failed: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Verify database credentials are correct")
        print("2. Check if database server is accessible from your network")
        print("3. Ensure the 'mystorybuddy' database exists")
        print("4. Check if your IP is whitelisted in RDS security group")
        return False
        
    finally:
        # Clean up
        if db_manager.pool:
            await db_manager.close()

if __name__ == "__main__":
    print("Starting database connectivity test...")
    print("Make sure to set DB_PASSWORD environment variable first:")
    print("export DB_PASSWORD='your_database_password'")
    print()
    
    # Run the test
    success = asyncio.run(test_database_connectivity())
    
    if success:
        exit(0)
    else:
        exit(1)