import os
import logging
import aiomysql
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# Database configuration
def get_db_config():
    return {
        'host': 'database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com',
        'port': 3306,
        'user': os.getenv('DB_USER', 'admin'),  # Default to 'admin', override with env var
        'password': os.getenv('DB_PASSWORD', 'mystorybuddydb123'),   # Default password
        'db': os.getenv('DB_NAME', 'mystorybuddy'),  # Default database name
        'charset': 'utf8mb4',
        'autocommit': True
    }

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        
    async def initialize(self):
        """Initialize database connection pool."""
        try:
            db_config = get_db_config()
            logger.info("Initializing database connection pool...")
            logger.info(f"Connecting to database at {db_config['host']}:{db_config['port']}")
            
            # Check if password is set
            if not db_config['password']:
                logger.error("DB_PASSWORD environment variable not set!")
                raise ValueError("Database password not configured")
            
            self.pool = await aiomysql.create_pool(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                db=db_config['db'],
                charset=db_config['charset'],
                autocommit=db_config['autocommit'],
                minsize=1,
                maxsize=10,
                echo=False,
                # Connection settings for better reliability
                pool_recycle=3600,  # Recycle connections every hour
                connect_timeout=60,  # Connection timeout
            )
            
            # Test the connection
            await self.test_connection()
            logger.info("Database connection pool initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            logger.error("Please ensure:")
            logger.error("1. DB_PASSWORD environment variable is set")
            logger.error("2. Database server is accessible")
            logger.error("3. Database credentials are correct")
            logger.error("4. Database 'mystorybuddy' exists")
            self.pool = None
            
    async def test_connection(self):
        """Test database connectivity."""
        if not self.pool:
            raise Exception("Database pool not initialized")
            
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1 as test")
                result = await cursor.fetchone()
                logger.info(f"Database connectivity test successful: {result}")
                
    async def reconnect(self):
        """Reconnect to the database by recreating the connection pool."""
        try:
            logger.info("Attempting to reconnect to database...")
            await self.close()
            await self.initialize()
            logger.info("Database reconnection successful")
        except Exception as e:
            logger.error(f"Database reconnection failed: {str(e)}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connection pool closed")
            
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool with retry logic."""
        if not self.pool:
            raise Exception("Database not initialized. Call initialize() first.")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.pool.acquire() as conn:
                    # Test the connection before using it
                    try:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            await cursor.fetchone()
                    except Exception as ping_error:
                        logger.warning(f"Connection ping failed on attempt {attempt + 1}: {ping_error}")
                        if attempt < max_retries - 1:
                            continue
                        raise
                    
                    yield conn
                    break
            except Exception as e:
                logger.error(f"Database connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying database connection in 1 second...")
                    import asyncio
                    await asyncio.sleep(1)
                    continue
                raise
                
    async def execute_query(self, query: str, params: tuple = None) -> list:
        """Execute a SELECT query and return results."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params or ())
                return await cursor.fetchall()
                
    async def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params or ())
                return cursor.rowcount

# Global database manager instance
db_manager = DatabaseManager()

# Database tables setup
async def create_tables():
    """Create necessary database tables if they don't exist."""
    try:
        logger.info("Creating database tables...")
        
        # Stories table
        stories_table = """
        CREATE TABLE IF NOT EXISTS stories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            story_content TEXT NOT NULL,
            prompt TEXT,
            image_urls JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            user_id VARCHAR(100),
            formats JSON,
            request_id VARCHAR(100),
            status ENUM('IN_PROGRESS', 'NEW', 'VIEWED') DEFAULT 'IN_PROGRESS',
            INDEX idx_created_at (created_at),
            INDEX idx_user_id (user_id),
            INDEX idx_request_id (request_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # Fun facts table
        fun_facts_table = """
        CREATE TABLE IF NOT EXISTS fun_facts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            prompt TEXT,
            facts JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            request_id VARCHAR(100),
            INDEX idx_created_at (created_at),
            INDEX idx_request_id (request_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # User sessions table (for tracking usage)
        sessions_table = """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(100) NOT NULL,
            user_id VARCHAR(100),
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_user_id (user_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # User avatars table for personalization feature
        avatars_table = """
        CREATE TABLE IF NOT EXISTS user_avatars (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            avatar_name VARCHAR(255) NOT NULL,
            traits_description TEXT,
            s3_image_url VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_created_at (created_at),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # Execute table creation
        await db_manager.execute_update(stories_table)
        await db_manager.execute_update(fun_facts_table)
        await db_manager.execute_update(sessions_table)
        await db_manager.execute_update(avatars_table)
        
        # Run migrations for existing tables
        await run_migrations()
        
        logger.info("Database tables created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

async def run_migrations():
    """Run database migrations for schema updates."""
    try:
        logger.info("Running database migrations...")
        
        # Migration 1: Add status column to stories table if it doesn't exist
        try:
            await db_manager.execute_update("""
                ALTER TABLE stories 
                ADD COLUMN status ENUM('IN_PROGRESS', 'NEW', 'VIEWED') DEFAULT 'IN_PROGRESS'
            """)
            logger.info("Added status column to stories table")
        except Exception as e:
            if "Duplicate column name" in str(e):
                logger.info("Status column already exists in stories table")
            else:
                logger.warning(f"Error adding status column: {str(e)}")
        
        # Migration 2: Add index for status column
        try:
            await db_manager.execute_update("""
                ALTER TABLE stories ADD INDEX idx_status (status)
            """)
            logger.info("Added index for status column")
        except Exception as e:
            if "Duplicate key name" in str(e):
                logger.info("Status index already exists")
            else:
                logger.warning(f"Error adding status index: {str(e)}")
        
        # Migration 3: Add status column to user_avatars table
        try:
            await db_manager.execute_update("""
                ALTER TABLE user_avatars 
                ADD COLUMN status ENUM('IN_PROGRESS', 'COMPLETED', 'FAILED') DEFAULT 'COMPLETED'
            """)
            logger.info("Added status column to user_avatars table")
        except Exception as e:
            if "Duplicate column name" in str(e):
                logger.info("Status column already exists in user_avatars table")
            else:
                logger.warning(f"Error adding avatar status column: {str(e)}")
        
        # Migration 4: Add index for avatar status column
        try:
            await db_manager.execute_update("""
                ALTER TABLE user_avatars ADD INDEX idx_avatar_status (status)
            """)
            logger.info("Added index for avatar status column")
        except Exception as e:
            if "Duplicate key name" in str(e):
                logger.info("Avatar status index already exists")
            else:
                logger.warning(f"Error adding avatar status index: {str(e)}")
        
        # Migration 5: Modify s3_image_url to allow empty strings and set default
        try:
            await db_manager.execute_update("""
                ALTER TABLE user_avatars 
                MODIFY COLUMN s3_image_url VARCHAR(500) DEFAULT ''
            """)
            logger.info("Modified s3_image_url column to allow empty defaults")
        except Exception as e:
            logger.warning(f"Error modifying s3_image_url column: {str(e)}")
        
        # Migration 6: Add visual_traits column to store extracted visual features
        try:
            await db_manager.execute_update("""
                ALTER TABLE user_avatars 
                ADD COLUMN visual_traits TEXT DEFAULT NULL
            """)
            logger.info("Added visual_traits column to user_avatars table")
        except Exception as e:
            if "Duplicate column name" in str(e):
                logger.info("Visual_traits column already exists in user_avatars table")
            else:
                logger.warning(f"Error adding visual_traits column: {str(e)}")
        
        logger.info("Database migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        raise

async def save_story(title: str, story_content: str, prompt: str, image_urls: list, 
                    formats: list, request_id: str, user_id: str = None, status: str = 'NEW') -> int:
    """Save a generated story to the database."""
    try:
        query = """
        INSERT INTO stories (title, story_content, prompt, image_urls, formats, request_id, user_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        import json
        params = (
            title,
            story_content,
            prompt,
            json.dumps(image_urls),
            json.dumps(formats),
            request_id,
            user_id,
            status
        )
        
        await db_manager.execute_update(query, params)
        logger.info(f"Story saved successfully for request_id: {request_id}")
        
        # Get the inserted ID
        result = await db_manager.execute_query("SELECT LAST_INSERT_ID() as id")
        return result[0]['id'] if result else None
        
    except Exception as e:
        logger.error(f"Error saving story: {str(e)}")
        raise

async def save_fun_facts(prompt: str, facts: list, request_id: str) -> int:
    """Save generated fun facts to the database."""
    try:
        query = """
        INSERT INTO fun_facts (prompt, facts, request_id)
        VALUES (%s, %s, %s)
        """
        
        import json
        params = (prompt, json.dumps(facts), request_id)
        
        await db_manager.execute_update(query, params)
        logger.info(f"Fun facts saved successfully for request_id: {request_id}")
        
        # Get the inserted ID
        result = await db_manager.execute_query("SELECT LAST_INSERT_ID() as id")
        return result[0]['id'] if result else None
        
    except Exception as e:
        logger.error(f"Error saving fun facts: {str(e)}")
        raise

async def get_recent_stories(limit: int = 10, user_id: str = None) -> list:
    """Get recent stories from the database."""
    try:
        if user_id:
            query = """
            SELECT id, title, story_content, prompt, image_urls, formats, created_at
            FROM stories 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT %s
            """
            params = (user_id, limit)
        else:
            query = """
            SELECT id, title, story_content, prompt, image_urls, formats, created_at
            FROM stories 
            ORDER BY created_at DESC 
            LIMIT %s
            """
            params = (limit,)
            
        results = await db_manager.execute_query(query, params)
        
        # Parse JSON fields
        import json
        for result in results:
            if result['image_urls']:
                result['image_urls'] = json.loads(result['image_urls'])
            if result['formats']:
                result['formats'] = json.loads(result['formats'])
                
        return results
        
    except Exception as e:
        logger.error(f"Error fetching recent stories: {str(e)}")
        return []

async def create_story_placeholder(prompt: str, formats: list, request_id: str, user_id: str = None) -> int:
    """Create a placeholder story entry with IN_PROGRESS status."""
    try:
        query = """
        INSERT INTO stories (title, story_content, prompt, image_urls, formats, request_id, user_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        import json
        params = (
            "Story in Progress...",  # Placeholder title
            "Your story is being generated...",  # Placeholder content
            prompt,
            json.dumps([]),  # Empty image URLs initially
            json.dumps(formats),
            request_id,
            user_id,
            'IN_PROGRESS'
        )
        
        result = await db_manager.execute_update(query, params)
        logger.info(f"Story placeholder created for request_id: {request_id}")
        
        # Get the inserted ID - check if execute_update returns it
        if hasattr(result, 'lastrowid') and result.lastrowid:
            return result.lastrowid
        
        # Fallback: query for the ID using request_id
        id_result = await db_manager.execute_query("SELECT id FROM stories WHERE request_id = %s", (request_id,))
        return id_result[0]['id'] if id_result else None
        
    except Exception as e:
        logger.error(f"Error creating story placeholder: {str(e)}")
        raise

async def update_story_content(story_id: int, title: str, story_content: str, image_urls: list, status: str = 'NEW') -> bool:
    """Update story content and mark as complete."""
    try:
        query = """
        UPDATE stories 
        SET title = %s, story_content = %s, image_urls = %s, status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        
        import json
        params = (
            title,
            story_content,
            json.dumps(image_urls),
            status,
            story_id
        )
        
        affected_rows = await db_manager.execute_update(query, params)
        if affected_rows > 0:
            logger.info(f"Story content updated for story_id: {story_id}")
            return True
        else:
            logger.warning(f"No story found with id: {story_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error updating story content: {str(e)}")
        raise

async def update_story_status(story_id: int, status: str) -> bool:
    """Update story status."""
    try:
        query = """
        UPDATE stories 
        SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        
        params = (status, story_id)
        
        affected_rows = await db_manager.execute_update(query, params)
        if affected_rows > 0:
            logger.info(f"Story status updated to {status} for story_id: {story_id}")
            return True
        else:
            logger.warning(f"No story found with id: {story_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error updating story status: {str(e)}")
        raise

async def get_story_by_id(story_id: int) -> dict:
    """Get a story by its ID."""
    try:
        query = """
        SELECT id, title, story_content, prompt, image_urls, formats, created_at, updated_at, status
        FROM stories 
        WHERE id = %s
        """
        
        results = await db_manager.execute_query(query, (story_id,))
        
        if results:
            import json
            result = results[0]
            if result['image_urls']:
                result['image_urls'] = json.loads(result['image_urls'])
            if result['formats']:
                result['formats'] = json.loads(result['formats'])
            return result
        else:
            return None
        
    except Exception as e:
        logger.error(f"Error fetching story by ID: {str(e)}")
        return None

async def get_stories_with_status(user_id: str = None, limit: int = 10) -> list:
    """Get recent stories with status information."""
    try:
        if user_id:
            query = """
            SELECT id, title, story_content, prompt, image_urls, formats, created_at, updated_at, status
            FROM stories 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT %s
            """
            params = (user_id, limit)
        else:
            query = """
            SELECT id, title, story_content, prompt, image_urls, formats, created_at, updated_at, status
            FROM stories 
            ORDER BY created_at DESC 
            LIMIT %s
            """
            params = (limit,)
            
        results = await db_manager.execute_query(query, params)
        
        # Parse JSON fields
        import json
        for result in results:
            if result['image_urls']:
                result['image_urls'] = json.loads(result['image_urls'])
            if result['formats']:
                result['formats'] = json.loads(result['formats'])
                
        return results
        
    except Exception as e:
        logger.error(f"Error fetching stories with status: {str(e)}")
        return []

async def get_new_stories_count(user_id: str = None) -> int:
    """Get count of new/unread stories for a user."""
    try:
        if user_id:
            query = """
            SELECT COUNT(*) as count
            FROM stories 
            WHERE user_id = %s AND status = 'NEW'
            """
            params = (user_id,)
        else:
            query = """
            SELECT COUNT(*) as count
            FROM stories 
            WHERE status = 'NEW'
            """
            params = ()
            
        results = await db_manager.execute_query(query, params)
        return results[0]['count'] if results else 0
        
    except Exception as e:
        logger.error(f"Error getting new stories count: {str(e)}")
        return 0

# Avatar management functions
async def create_user_avatar(user_id: int, avatar_name: str, traits_description: str, s3_image_url: str = "", status: str = "COMPLETED", visual_traits: str = None) -> int:
    """Create or update user avatar (limit one per user)."""
    try:
        logger.info(f"Creating avatar for user_id: {user_id}, name: {avatar_name}, status: {status}")
        
        # Verify user exists first
        user_check = await db_manager.execute_query(
            "SELECT id FROM users WHERE id = %s", (user_id,)
        )
        if not user_check:
            logger.error(f"User with id {user_id} does not exist")
            raise ValueError(f"User with id {user_id} does not exist")
        
        # First, deactivate any existing avatars for this user
        deactivated_rows = await db_manager.execute_update(
            "UPDATE user_avatars SET is_active = FALSE WHERE user_id = %s",
            (user_id,)
        )
        logger.info(f"Deactivated {deactivated_rows} existing avatars for user_id: {user_id}")
        
        # Create new avatar and get the ID in one transaction
        query = """
        INSERT INTO user_avatars (user_id, avatar_name, traits_description, s3_image_url, status, visual_traits)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        params = (user_id, avatar_name, traits_description, s3_image_url or "", status, visual_traits)
        
        # Use a direct connection to get the insert ID
        async with db_manager.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                avatar_id = cursor.lastrowid
                logger.info(f"Insert executed, lastrowid: {avatar_id}, affected rows: {cursor.rowcount}")
                
                if not avatar_id:
                    # Try LAST_INSERT_ID() as backup
                    await cursor.execute("SELECT LAST_INSERT_ID() as id")
                    result = await cursor.fetchone()
                    avatar_id = result[0] if result else None
                    logger.info(f"LAST_INSERT_ID() backup returned: {avatar_id}")
                
                if not avatar_id:
                    logger.error(f"Failed to get avatar_id after insert for user_id: {user_id}")
                    raise ValueError("Failed to get avatar_id after insert")
        
        logger.info(f"Avatar created for user_id: {user_id}, avatar_id: {avatar_id}, status: {status}")
        return avatar_id
        
    except Exception as e:
        logger.error(f"Error creating user avatar: {str(e)}")
        logger.error(f"Parameters: user_id={user_id}, avatar_name={avatar_name}, status={status}")
        raise

async def update_avatar_status(avatar_id: int, status: str, s3_image_url: str = None) -> bool:
    """Update avatar status and optionally the S3 URL when completed."""
    try:
        if s3_image_url:
            query = """
            UPDATE user_avatars 
            SET status = %s, s3_image_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            params = (status, s3_image_url, avatar_id)
        else:
            query = """
            UPDATE user_avatars 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            params = (status, avatar_id)
        
        await db_manager.execute_update(query, params)
        logger.info(f"Avatar {avatar_id} status updated to: {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating avatar status: {str(e)}")
        raise

async def update_avatar_status_with_traits(avatar_id: int, status: str, s3_image_url: str = None, visual_traits: str = None) -> bool:
    """Update avatar status, S3 URL, and visual traits when generation is completed."""
    try:
        if s3_image_url and visual_traits:
            query = """
            UPDATE user_avatars 
            SET status = %s, s3_image_url = %s, visual_traits = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            params = (status, s3_image_url, visual_traits, avatar_id)
        elif s3_image_url:
            query = """
            UPDATE user_avatars 
            SET status = %s, s3_image_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            params = (status, s3_image_url, avatar_id)
        else:
            query = """
            UPDATE user_avatars 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            params = (status, avatar_id)
        
        await db_manager.execute_update(query, params)
        logger.info(f"Avatar {avatar_id} status updated to: {status} with visual traits")
        return True
        
    except Exception as e:
        logger.error(f"Error updating avatar status with traits: {str(e)}")
        raise

async def get_completed_avatars_count(user_id: int) -> int:
    """Get count of completed avatars that haven't been viewed (similar to new stories)."""
    try:
        query = """
        SELECT COUNT(*) as count 
        FROM user_avatars 
        WHERE user_id = %s AND status = 'COMPLETED' AND is_active = TRUE
        """
        result = await db_manager.execute_query(query, (user_id,))
        return result[0]['count'] if result else 0
    except Exception as e:
        logger.error(f"Error getting completed avatars count: {str(e)}")
        return 0

async def get_user_avatar(user_id: int) -> dict:
    """Get user's active avatar."""
    try:
        query = """
        SELECT id, avatar_name, traits_description, s3_image_url, status, visual_traits, created_at, updated_at
        FROM user_avatars 
        WHERE user_id = %s AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        results = await db_manager.execute_query(query, (user_id,))
        return results[0] if results else None
        
    except Exception as e:
        logger.error(f"Error fetching user avatar: {str(e)}")
        return None

async def get_user_avatar_by_name(user_id: int, avatar_name: str) -> dict:
    """Get user's avatar by name for story generation."""
    try:
        query = """
        SELECT id, avatar_name, traits_description, visual_traits, s3_image_url, status, created_at, updated_at
        FROM user_avatars 
        WHERE user_id = %s AND avatar_name = %s AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        results = await db_manager.execute_query(query, (user_id, avatar_name))
        return results[0] if results else None
        
    except Exception as e:
        logger.error(f"Error fetching user avatar by name: {str(e)}")
        return None

async def update_user_avatar(user_id: int, avatar_name: str = None, traits_description: str = None) -> bool:
    """Update user avatar details (not image)."""
    try:
        # Build dynamic update query
        update_fields = []
        params = []
        
        if avatar_name is not None:
            update_fields.append("avatar_name = %s")
            params.append(avatar_name)
            
        if traits_description is not None:
            update_fields.append("traits_description = %s")
            params.append(traits_description)
            
        if not update_fields:
            return False
            
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        
        query = f"""
        UPDATE user_avatars 
        SET {', '.join(update_fields)}
        WHERE user_id = %s AND is_active = TRUE
        """
        
        affected_rows = await db_manager.execute_update(query, tuple(params))
        if affected_rows > 0:
            logger.info(f"Avatar updated for user_id: {user_id}")
            return True
        else:
            logger.warning(f"No active avatar found for user_id: {user_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error updating user avatar: {str(e)}")
        raise

async def cleanup_invalid_stories() -> dict:
    """Clean up stories with invalid or blank image URLs."""
    try:
        logger.info("Starting cleanup of invalid stories...")
        
        # First, get count of stories to be cleaned up
        count_query = """
        SELECT COUNT(*) as count FROM stories 
        WHERE (
            image_urls = '[]' OR 
            image_urls = '' OR 
            image_urls IS NULL OR
            image_urls LIKE '%placeholder%' OR
            image_urls LIKE '%Comic+Generation+Failed%' OR
            image_urls LIKE '%Image+Upload+Disabled%' OR
            image_urls LIKE '%No+Image+Data%' OR
            title = 'Story in Progress...' OR
            story_content = 'Your story is being generated...'
        )
        """
        
        count_result = await db_manager.execute_query(count_query)
        count_to_delete = count_result[0]['count'] if count_result else 0
        
        if count_to_delete == 0:
            logger.info("No invalid stories found to clean up")
            return {"deleted_count": 0, "message": "No invalid stories found"}
        
        # Delete invalid stories
        delete_query = """
        DELETE FROM stories 
        WHERE (
            image_urls = '[]' OR 
            image_urls = '' OR 
            image_urls IS NULL OR
            image_urls LIKE '%placeholder%' OR
            image_urls LIKE '%Comic+Generation+Failed%' OR
            image_urls LIKE '%Image+Upload+Disabled%' OR
            image_urls LIKE '%No+Image+Data%' OR
            title = 'Story in Progress...' OR
            story_content = 'Your story is being generated...'
        )
        """
        
        deleted_rows = await db_manager.execute_update(delete_query)
        
        logger.info(f"Cleaned up {deleted_rows} invalid stories from database")
        
        return {
            "deleted_count": deleted_rows,
            "message": f"Successfully cleaned up {deleted_rows} invalid stories"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up invalid stories: {str(e)}")
        raise