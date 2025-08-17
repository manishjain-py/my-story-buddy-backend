"""
Authentication routes for My Story Buddy
Handles signup, login, OTP, and Google OAuth endpoints
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
import re

from auth.auth_models import (
    UserSignup, UserLogin, OTPRequest, OTPVerification, 
    Token, UserDatabase, AuthType
)
from auth.auth_utils import (
    PasswordUtils, JWTUtils, OTPUtils, ValidationUtils,
    create_user_token, get_current_user, security
)
from core.email_service import email_service

logger = logging.getLogger(__name__)

# Create router
auth_router = APIRouter(prefix="/auth", tags=["authentication"])

@auth_router.post("/signup", response_model=Token)
async def signup(user_data: UserSignup, request: Request):
    """
    Register a new user with email and password
    """
    try:
        # Validate email format
        if not ValidationUtils.is_valid_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password strength
        is_strong, error_msg = ValidationUtils.is_strong_password(user_data.password)
        if not is_strong:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Sanitize name inputs
        first_name = ValidationUtils.sanitize_name(user_data.first_name)
        last_name = ValidationUtils.sanitize_name(user_data.last_name)
        
        if not first_name or not last_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First name and last name are required"
            )
        
        # Check if user already exists
        existing_user = await UserDatabase.get_user_by_email(user_data.email.lower())
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Hash password
        password_hash = PasswordUtils.hash_password(user_data.password)
        
        # Create user in database
        logger.info(f"Creating user account for: {user_data.email}")
        user_id = await UserDatabase.create_user(
            email=user_data.email.lower(),
            first_name=first_name,
            last_name=last_name,
            password_hash=password_hash,
            auth_type=AuthType.EMAIL_PASSWORD
        )
        
        logger.info(f"User creation result - user_id: {user_id}")
        
        if not user_id:
            logger.error(f"create_user returned None for email: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
        
        # Get the created user
        logger.info(f"Retrieving created user with ID: {user_id}")
        user = await UserDatabase.get_user_by_id(user_id)
        if not user:
            logger.error(f"Failed to retrieve user with ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created user"
            )
        
        logger.info(f"User retrieved successfully: {user['email']}")
        
        # Send welcome email (don't wait for it)
        try:
            await email_service.send_welcome_email(user_data.email, first_name)
        except Exception as e:
            logger.warning(f"Failed to send welcome email: {str(e)}")
        
        # Create authentication token
        logger.info(f"Creating authentication token for user: {user['email']}")
        token_data = await create_user_token(user)
        logger.info(f"Token created successfully for user: {user['email']}")
        
        logger.info(f"User signup successful: {user_data.email}")
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=token_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during signup"
        )

@auth_router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, request: Request):
    """
    Login user with email and password
    """
    try:
        # Validate email format
        if not ValidationUtils.is_valid_email(user_credentials.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Get user from database
        user = await UserDatabase.get_user_by_email(user_credentials.email.lower())
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if user has a password (might be OAuth-only user)
        if not user['password_hash']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account uses a different login method. Please use OTP or Google login."
            )
        
        # Verify password
        if not PasswordUtils.verify_password(user_credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create authentication token
        token_data = await create_user_token(user)
        
        logger.info(f"User login successful: {user_credentials.email}")
        
        return JSONResponse(content=token_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@auth_router.post("/send-otp")
async def send_otp(otp_request: OTPRequest, request: Request):
    """
    Send OTP to user's email for authentication
    """
    try:
        # Validate email format
        if not ValidationUtils.is_valid_email(otp_request.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        email = otp_request.email.lower()
        
        # Check if user exists
        user = await UserDatabase.get_user_by_email(email)
        first_name = user['first_name'] if user else None
        
        # Generate OTP
        otp = OTPUtils.generate_secure_otp(6)
        
        # Store OTP in database (expires in 5 minutes)
        await UserDatabase.store_otp(email, otp, expires_in_minutes=5)
        
        # Send OTP email
        email_sent = await email_service.send_otp_email(email, otp, first_name)
        
        if not email_sent:
            logger.error(f"Failed to send OTP email to {email}")
            # Still return success to prevent email enumeration
        
        logger.info(f"OTP sent to: {email}")
        
        return JSONResponse(
            content={
                "message": "OTP sent to your email address",
                "expires_in": 300  # 5 minutes in seconds
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP"
        )

@auth_router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_verification: OTPVerification, request: Request):
    """
    Verify OTP and login/create user
    """
    try:
        # Validate email format
        if not ValidationUtils.is_valid_email(otp_verification.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate OTP format (should be 6 digits)
        if not re.match(r'^\d{6}$', otp_verification.otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP format"
            )
        
        email = otp_verification.email.lower()
        
        # Verify OTP
        is_valid = await UserDatabase.verify_otp(email, otp_verification.otp)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP"
            )
        
        # Check if user exists
        user = await UserDatabase.get_user_by_email(email)
        
        if not user:
            # Create new user with OTP auth type
            # Extract first name from email or use default
            email_parts = email.split('@')[0]
            first_name = email_parts.capitalize() if email_parts else "User"
            
            user_id = await UserDatabase.create_user(
                email=email,
                first_name=first_name,
                last_name="",
                auth_type=AuthType.OTP
            )
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account"
                )
            
            user = await UserDatabase.get_user_by_id(user_id)
            
            # Send welcome email for new users
            try:
                await email_service.send_welcome_email(email, first_name)
            except Exception as e:
                logger.warning(f"Failed to send welcome email: {str(e)}")
        
        # Create authentication token
        token_data = await create_user_token(user)
        
        logger.info(f"OTP verification successful: {email}")
        
        return JSONResponse(content=token_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during OTP verification"
        )

@auth_router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout user and invalidate session
    """
    try:
        # Invalidate the session token
        await UserDatabase.invalidate_auth_session(credentials.credentials)
        
        return JSONResponse(
            content={"message": "Logged out successfully"}
        )
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        # Even if there's an error, we can still return success
        # as the client will discard the token anyway
        return JSONResponse(
            content={"message": "Logged out successfully"}
        )

@auth_router.get("/me", response_model=dict)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user information
    """
    try:
        from auth.auth_models import UserResponse, AuthType
        
        user_response = UserResponse(
            id=current_user["id"],
            email=current_user["email"],
            first_name=current_user["first_name"],
            last_name=current_user["last_name"],
            auth_type=AuthType(current_user["auth_type"]),
            created_at=current_user["created_at"],
            is_active=current_user["is_active"]
        )
        
        return user_response.dict()
        
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )

@auth_router.delete("/delete-account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """
    Permanently delete user account and all associated data
    
    This endpoint provides complete account deletion as required by App Store guidelines.
    All user data including stories, avatars, and account information will be permanently removed.
    """
    try:
        user_id = current_user["id"]
        user_email = current_user["email"]
        
        logger.info(f"Starting account deletion for user ID: {user_id}, email: {user_email}")
        
        # Delete user account and all associated data
        deletion_successful = await UserDatabase.delete_user_account(user_id)
        
        if not deletion_successful:
            logger.error(f"Failed to delete account for user ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete account. Please try again or contact support."
            )
        
        logger.info(f"Account deletion successful for user ID: {user_id}, email: {user_email}")
        
        return JSONResponse(
            content={
                "message": "Account successfully deleted",
                "timestamp": datetime.now().isoformat(),
                "note": "All account data has been permanently removed and cannot be recovered"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account deletion error for user {current_user.get('id', 'unknown')}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during account deletion"
        )

# Health check endpoint for authentication service
@auth_router.get("/health")
async def auth_health_check():
    """
    Health check for authentication service
    """
    try:
        # Test database connection
        await UserDatabase.get_user_by_id(1)  # This will either work or throw an exception
        
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "authentication",
                "database": "connected",
                "timestamp": "2025-06-21"
            }
        )
        
    except Exception as e:
        logger.error(f"Auth health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "authentication",
                "database": "disconnected",
                "error": str(e)
            }
        )