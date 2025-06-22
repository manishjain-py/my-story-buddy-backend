"""
Authentication utilities for My Story Buddy
Handles password hashing, JWT tokens, and security utilities
"""
import os
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import random

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# Password hashing (using pbkdf2_sha256 which is Lambda-compatible)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class PasswordUtils:
    """Utilities for password hashing and verification"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using pbkdf2_sha256"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_random_password(length: int = 12) -> str:
        """Generate a random password for OAuth users"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

class JWTUtils:
    """Utilities for JWT token creation and verification"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def extract_user_id_from_token(token: str) -> Optional[int]:
        """Extract user ID from JWT token"""
        payload = JWTUtils.verify_token(token)
        if payload:
            return payload.get("user_id")
        return None

class OTPUtils:
    """Utilities for OTP generation and management"""
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a random OTP of specified length"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def generate_secure_otp(length: int = 6) -> str:
        """Generate a cryptographically secure OTP"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))

class SessionUtils:
    """Utilities for session management"""
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def extract_device_info(user_agent: str) -> str:
        """Extract device information from user agent"""
        # Simple device info extraction
        if not user_agent:
            return "Unknown Device"
        
        user_agent_lower = user_agent.lower()
        
        if "mobile" in user_agent_lower or "android" in user_agent_lower:
            return "Mobile Device"
        elif "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            return "iOS Device"
        elif "windows" in user_agent_lower:
            return "Windows Computer"
        elif "mac" in user_agent_lower:
            return "Mac Computer"
        elif "linux" in user_agent_lower:
            return "Linux Computer"
        else:
            return "Unknown Device"

class ValidationUtils:
    """Utilities for input validation"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def is_strong_password(password: str) -> tuple[bool, str]:
        """
        Check if password meets strength requirements
        Returns (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        return True, ""
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize first/last name input"""
        # Remove extra whitespace and limit length
        return name.strip()[:50] if name else ""

# Token creation helper
async def create_user_token(user_data: dict) -> dict:
    """Create authentication token for user"""
    from auth_models import UserResponse, AuthType
    
    # Create JWT payload
    token_data = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "auth_type": user_data["auth_type"]
    }
    
    # Generate access token
    access_token = JWTUtils.create_access_token(token_data)
    
    # Create session token for database tracking
    session_token = SessionUtils.generate_session_token()
    
    # Store session in database
    from auth_models import UserDatabase
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    await UserDatabase.create_auth_session(
        user_id=user_data["id"],
        session_token=session_token,
        expires_at=expires_at
    )
    
    # Update last login
    await UserDatabase.update_last_login(user_data["id"])
    
    # Prepare user response
    user_response = UserResponse(
        id=user_data["id"],
        email=user_data["email"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        auth_type=AuthType(user_data["auth_type"]),
        created_at=user_data["created_at"],
        is_active=user_data["is_active"]
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": {
            "id": user_response.id,
            "email": user_response.email,
            "first_name": user_response.first_name,
            "last_name": user_response.last_name,
            "auth_type": user_response.auth_type.value,
            "created_at": user_response.created_at.isoformat(),
            "is_active": user_response.is_active
        }
    }

# Dependency for protecting routes
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current authenticated user
    Use this to protect routes that require authentication
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify JWT token
        payload = JWTUtils.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        from auth_models import UserDatabase
        user = await UserDatabase.get_user_by_id(user_id)
        if user is None:
            raise credentials_exception
        
        return user
        
    except Exception as e:
        raise credentials_exception

async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """
    Dependency to get current authenticated user (optional)
    Returns None if not authenticated, instead of raising an exception
    """
    try:
        # Verify JWT token
        payload = JWTUtils.verify_token(credentials.credentials)
        if payload is None:
            return None
        
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        
        # Get user from database
        from auth_models import UserDatabase
        user = await UserDatabase.get_user_by_id(user_id)
        return user
        
    except Exception:
        return None

from fastapi.security.utils import get_authorization_scheme_param
from fastapi import Request

async def get_optional_user(request: Request) -> Optional[dict]:
    """
    Dependency to get current user if authenticated, None otherwise
    Use this for routes that work with or without authentication
    """
    try:
        # Try to get authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
            
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return None
            
        # Verify JWT token
        payload = JWTUtils.verify_token(token)
        if payload is None:
            return None
        
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        
        # Get user from database
        from auth_models import UserDatabase
        user = await UserDatabase.get_user_by_id(user_id)
        return user
        
    except Exception:
        return None