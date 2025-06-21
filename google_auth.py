"""
Google OAuth authentication for My Story Buddy
"""
import os
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException, status, Request
from authlib.integrations.starlette_client import OAuth

from auth_models import UserDatabase, AuthType
from auth_utils import create_user_token
from email_service import email_service

logger = logging.getLogger(__name__)

class GoogleOAuth:
    """Google OAuth handler"""
    
    def __init__(self):
        self.oauth = OAuth()
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8003/auth/google/callback')
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
            self.enabled = False
        else:
            self.enabled = True
            self._setup_oauth()
    
    def _setup_oauth(self):
        """Setup OAuth client"""
        try:
            self.oauth.register(
                name='google',
                client_id=self.client_id,
                client_secret=self.client_secret,
                server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
                client_kwargs={
                    'scope': 'openid email profile',
                    'prompt': 'select_account',  # Force account selection
                }
            )
            logger.info("Google OAuth client configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup Google OAuth: {str(e)}")
            self.enabled = False
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate Google OAuth authorization URL"""
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth not configured"
            )
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'openid email profile',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'select_account',
            'include_granted_scopes': 'true'
        }
        
        if state:
            params['state'] = state
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return auth_url
    
    async def handle_callback(self, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Handle Google OAuth callback"""
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth not configured"
            )
        
        try:
            # Exchange code for tokens
            token_data = await self._exchange_code_for_tokens(code)
            
            # Get user info from Google
            user_info = await self._get_google_user_info(token_data['access_token'])
            
            # Process user authentication
            token_response = await self._process_google_user(user_info)
            
            return token_response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Google OAuth callback error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process Google authentication"
            )
    
    async def _exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://oauth2.googleapis.com/token',
                    data={
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'code': code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': self.redirect_uri,
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to exchange authorization code"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Token exchange request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to communicate with Google"
            )
    
    async def _get_google_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://www.googleapis.com/oauth2/v2/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if response.status_code != 200:
                    logger.error(f"User info request failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to get user information from Google"
                    )
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"User info request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user information"
            )
    
    async def _process_google_user(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process Google user and create/login user"""
        try:
            google_id = user_info.get('id')
            email = user_info.get('email', '').lower()
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            
            if not google_id or not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user information from Google"
                )
            
            # Check if user exists by Google ID
            user = await UserDatabase.get_user_by_google_id(google_id)
            
            if not user:
                # Check if user exists by email
                user = await UserDatabase.get_user_by_email(email)
                
                if user:
                    # User exists with email but no Google ID - link accounts
                    # Update user with Google ID
                    from database import db_manager
                    await db_manager.execute_update(
                        "UPDATE users SET google_id = %s, auth_type = %s WHERE id = %s",
                        (google_id, AuthType.GOOGLE.value, user['id'])
                    )
                    user['google_id'] = google_id
                    user['auth_type'] = AuthType.GOOGLE.value
                else:
                    # Create new user
                    user_id = await UserDatabase.create_user(
                        email=email,
                        first_name=first_name or 'User',
                        last_name=last_name or '',
                        auth_type=AuthType.GOOGLE,
                        google_id=google_id
                    )
                    
                    if not user_id:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create user account"
                        )
                    
                    user = await UserDatabase.get_user_by_id(user_id)
                    
                    # Send welcome email for new users
                    try:
                        await email_service.send_welcome_email(email, first_name or 'User')
                    except Exception as e:
                        logger.warning(f"Failed to send welcome email: {str(e)}")
            
            # Create authentication token
            token_data = await create_user_token(user)
            
            logger.info(f"Google OAuth login successful: {email}")
            
            return token_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Process Google user error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process user authentication"
            )

# Global Google OAuth instance
google_oauth = GoogleOAuth()

# Google OAuth routes
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, JSONResponse

google_router = APIRouter(prefix="/auth/google", tags=["google-auth"])

@google_router.get("/")
async def google_login(request: Request):
    """
    Redirect to Google OAuth authorization
    """
    try:
        if not google_oauth.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth is not configured"
            )
        
        # Generate state parameter for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)
        
        # Store state in session if needed (for production, use proper session management)
        
        auth_url = google_oauth.get_authorization_url(state=state)
        
        return RedirectResponse(url=auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login redirect error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Google login"
        )

@google_router.get("/callback")
async def google_callback(request: Request):
    """
    Handle Google OAuth callback
    """
    try:
        # Get query parameters
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        
        if error:
            logger.warning(f"Google OAuth error: {error}")
            # Redirect to frontend with error
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
            return RedirectResponse(url=f"{frontend_url}/login?error=oauth_error")
        
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code not provided"
            )
        
        # Handle OAuth callback
        token_data = await google_oauth.handle_callback(code, state)
        
        # Redirect to frontend with token
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        
        # For development, you might want to redirect with the token in URL
        # In production, consider using secure cookies or session storage
        return RedirectResponse(
            url=f"{frontend_url}/auth/success?token={token_data['access_token']}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google callback error: {str(e)}")
        # Redirect to frontend with error
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        return RedirectResponse(url=f"{frontend_url}/login?error=auth_failed")

@google_router.get("/url")
async def get_google_auth_url(request: Request):
    """
    Get Google OAuth authorization URL (for frontend usage)
    """
    try:
        if not google_oauth.enabled:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Google OAuth not configured"}
            )
        
        # Generate state parameter
        import secrets
        state = secrets.token_urlsafe(32)
        
        auth_url = google_oauth.get_authorization_url(state=state)
        
        return JSONResponse(
            content={
                "auth_url": auth_url,
                "state": state
            }
        )
        
    except Exception as e:
        logger.error(f"Get Google auth URL error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to generate auth URL"}
        )