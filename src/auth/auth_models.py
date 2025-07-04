"""
Authentication models and database schema for My Story Buddy
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
from enum import Enum

logger = logging.getLogger(__name__)

# Enums
class AuthType(str, Enum):
    EMAIL_PASSWORD = "email_password"
    OTP = "otp"
    GOOGLE = "google"

# Pydantic Models for API requests/responses
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPRequest(BaseModel):
    email: EmailStr

class OTPVerification(BaseModel):
    email: EmailStr
    otp: str

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    auth_type: AuthType
    created_at: datetime
    is_active: bool

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

class GoogleAuthCallback(BaseModel):
    code: str
    state: Optional[str] = None

# Database operations
class UserDatabase:
    """Database operations for user management"""
    
    @staticmethod
    async def create_user_tables():
        """Create user-related database tables"""
        from core.database import db_manager
        
        # Users table
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            auth_type ENUM('email_password', 'otp', 'google') NOT NULL DEFAULT 'email_password',
            google_id VARCHAR(255) NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL,
            INDEX idx_email (email),
            INDEX idx_google_id (google_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # OTP table for temporary OTP storage
        otp_table = """
        CREATE TABLE IF NOT EXISTS user_otps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            otp_code VARCHAR(10) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_email (email),
            INDEX idx_expires_at (expires_at),
            INDEX idx_otp_code (otp_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # User sessions for JWT token management
        user_sessions_auth_table = """
        CREATE TABLE IF NOT EXISTS user_auth_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            session_token VARCHAR(500) NOT NULL,
            device_info TEXT,
            ip_address VARCHAR(45),
            expires_at TIMESTAMP NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_session_token (session_token),
            INDEX idx_expires_at (expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        await db_manager.execute_update(users_table)
        await db_manager.execute_update(otp_table)
        await db_manager.execute_update(user_sessions_auth_table)
    
    @staticmethod
    async def create_user(email: str, first_name: str, last_name: str, 
                         password_hash: Optional[str] = None, auth_type: AuthType = AuthType.EMAIL_PASSWORD,
                         google_id: Optional[str] = None) -> Optional[int]:
        """Create a new user in the database"""
        from core.database import db_manager
        
        query = """
        INSERT INTO users (email, password_hash, first_name, last_name, auth_type, google_id, is_verified)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # Auto-verify Google users
        is_verified = auth_type == AuthType.GOOGLE
        
        params = (email, password_hash, first_name, last_name, auth_type.value, google_id, is_verified)
        
        try:
            # Use the database manager's connection context to ensure same connection
            async with db_manager.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    user_id = cursor.lastrowid
                    
                    logger.info(f"User created successfully with ID: {user_id}")
                    return user_id
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            if "Duplicate entry" in str(e):
                logger.warning(f"User already exists with email: {email}")
                return None  # User already exists
            raise
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[dict]:
        """Get user by email address"""
        from core.database import db_manager
        
        query = """
        SELECT id, email, password_hash, first_name, last_name, auth_type, 
               google_id, is_active, is_verified, created_at, last_login
        FROM users 
        WHERE email = %s AND is_active = TRUE
        """
        
        result = await db_manager.execute_query(query, (email,))
        return result[0] if result else None
    
    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[dict]:
        """Get user by ID"""
        from core.database import db_manager
        
        query = """
        SELECT id, email, password_hash, first_name, last_name, auth_type, 
               google_id, is_active, is_verified, created_at, last_login
        FROM users 
        WHERE id = %s AND is_active = TRUE
        """
        
        result = await db_manager.execute_query(query, (user_id,))
        return result[0] if result else None
    
    @staticmethod
    async def get_user_by_google_id(google_id: str) -> Optional[dict]:
        """Get user by Google ID"""
        from core.database import db_manager
        
        query = """
        SELECT id, email, password_hash, first_name, last_name, auth_type, 
               google_id, is_active, is_verified, created_at, last_login
        FROM users 
        WHERE google_id = %s AND is_active = TRUE
        """
        
        result = await db_manager.execute_query(query, (google_id,))
        return result[0] if result else None
    
    @staticmethod
    async def update_last_login(user_id: int):
        """Update user's last login timestamp"""
        from core.database import db_manager
        
        query = "UPDATE users SET last_login = NOW() WHERE id = %s"
        await db_manager.execute_update(query, (user_id,))
    
    @staticmethod
    async def store_otp(email: str, otp_code: str, expires_in_minutes: int = 5):
        """Store OTP for email verification"""
        from core.database import db_manager
        
        # First, mark any existing OTPs for this email as used
        await db_manager.execute_update(
            "UPDATE user_otps SET is_used = TRUE WHERE email = %s AND is_used = FALSE",
            (email,)
        )
        
        # Store new OTP
        query = """
        INSERT INTO user_otps (email, otp_code, expires_at)
        VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL %s MINUTE))
        """
        
        await db_manager.execute_update(query, (email, otp_code, expires_in_minutes))
    
    @staticmethod
    async def verify_otp(email: str, otp_code: str) -> bool:
        """Verify OTP and mark as used"""
        from core.database import db_manager
        
        # Check if valid OTP exists
        query = """
        SELECT id FROM user_otps 
        WHERE email = %s AND otp_code = %s AND expires_at > NOW() AND is_used = FALSE
        """
        
        result = await db_manager.execute_query(query, (email, otp_code))
        
        if result:
            # Mark OTP as used
            await db_manager.execute_update(
                "UPDATE user_otps SET is_used = TRUE WHERE id = %s",
                (result[0]['id'],)
            )
            return True
        
        return False
    
    @staticmethod
    async def create_auth_session(user_id: int, session_token: str, expires_at: datetime,
                                 device_info: Optional[str] = None, ip_address: Optional[str] = None):
        """Create user authentication session"""
        from core.database import db_manager
        
        query = """
        INSERT INTO user_auth_sessions (user_id, session_token, device_info, ip_address, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        await db_manager.execute_update(query, (user_id, session_token, device_info, ip_address, expires_at))
    
    @staticmethod
    async def verify_auth_session(session_token: str) -> Optional[dict]:
        """Verify authentication session"""
        from core.database import db_manager
        
        query = """
        SELECT s.user_id, s.expires_at, u.email, u.first_name, u.last_name, u.auth_type, u.is_active
        FROM user_auth_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_token = %s AND s.expires_at > NOW() AND s.is_active = TRUE AND u.is_active = TRUE
        """
        
        result = await db_manager.execute_query(query, (session_token,))
        return result[0] if result else None
    
    @staticmethod
    async def invalidate_auth_session(session_token: str):
        """Invalidate authentication session"""
        from core.database import db_manager
        
        query = "UPDATE user_auth_sessions SET is_active = FALSE WHERE session_token = %s"
        await db_manager.execute_update(query, (session_token,))