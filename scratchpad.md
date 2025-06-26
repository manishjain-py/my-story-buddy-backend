# Personalization Feature Implementation - Development Notes

## Project Discovery (2025-06-26)

### Existing Architecture
- **Backend**: FastAPI with MySQL database (RDS), deployed on EC2 with Docker
- **Frontend**: React with Vite, deployed on S3/CloudFront
- **Authentication**: JWT-based with email/password, OTP, and Google OAuth
- **Database**: MySQL with existing tables: users, user_otps, user_auth_sessions, stories, fun_facts
- **Storage**: AWS S3 bucket `mystorybuddy-assets` for story images

### Key Files Discovered
- `main.py`: Main FastAPI app with story generation and S3 upload functionality
- `database.py`: Database manager with connection pooling and table management
- `auth_models.py`: User authentication models and database operations
- `App.jsx`: React frontend with authentication, story generation, and navigation

### Implementation Strategy
1. Create user_avatars table for storing avatar metadata
2. Add avatar upload API endpoint with GPT-4 Vision integration
3. Reuse existing S3 upload functionality for avatar images
4. Add Personalization page to frontend navigation
5. Create file upload UI with image preview and form inputs

### Database Schema Design
Need to create `user_avatars` table with:
- id (PRIMARY KEY)
- user_id (FOREIGN KEY to users.id)
- avatar_name (VARCHAR)
- traits_description (TEXT)
- s3_image_url (VARCHAR)
- created_at/updated_at (TIMESTAMP)
- is_active (BOOLEAN) - for future multi-avatar support

### API Endpoints to Add
- POST /personalization/avatar - Upload image and generate comic-style avatar
- GET /personalization/avatar - Get user's current avatar
- PUT /personalization/avatar - Update avatar details

### Frontend Components to Create
- PersonalizationPage.jsx - Main page component
- AvatarUpload.jsx - File upload with preview
- AvatarForm.jsx - Name and traits input form

## Gotchas & Considerations
- Limit to one avatar per user initially (check existing before allowing new upload)
- Use existing S3 upload patterns from story image generation
- Maintain same authentication patterns as existing My Stories feature
- Follow existing UI/CSS patterns for consistency
- Handle file size limits and image format validation
- GPT-4 Vision prompt needs clear instructions for comic-style avatar generation

## Questions to Address
1. What file size/format limits should we set for avatar uploads?
2. Should we allow avatar deletion/replacement or just updates?
3. What specific GPT-4 Vision prompt will generate good comic-style avatars?
4. Should avatars be used automatically in future story generation?

## Implementation Completed (2025-06-26)

### Backend Changes Made
1. **Database Schema**: Added `user_avatars` table to database.py with proper foreign key relationships
2. **API Endpoints**: Added 3 new endpoints in main.py:
   - POST /personalization/avatar - Upload and generate comic avatar
   - GET /personalization/avatar - Retrieve user's current avatar
   - PUT /personalization/avatar - Update avatar name/traits
3. **GPT-4 Vision Integration**: Two-step avatar generation:
   - Step 1: GPT-4 Vision analyzes uploaded photo and creates character description
   - Step 2: DALL-E 3 generates comic-style avatar based on description
4. **S3 Storage**: Reused existing S3 infrastructure with avatars/ directory for organization
5. **Authentication**: All endpoints require JWT authentication using existing auth system

### Frontend Changes Made
1. **PersonalizationPage Component**: Full-featured page with:
   - Image upload with preview
   - Form inputs for avatar name and personality traits
   - Display of existing avatar with edit capabilities
   - Loading states and error handling
2. **Navigation**: Added Personalization menu item (only visible to authenticated users)
3. **Styling**: Responsive CSS with consistent design patterns
4. **File Validation**: Client-side validation for file type and size (10MB limit)

### File Size and Format Decisions
- Max file size: 10MB (reasonable for user uploads)
- Supported formats: All image types (validated on both client and server)
- Generated avatars: 1024x1024 PNG format for high quality

### GPT-4 Vision Prompt Strategy
- Two-stage generation for better results
- First stage: Analyze photo and extract character features
- Second stage: Generate comic-style avatar with personality traits
- Emphasis on child-friendly, Pixar/Disney-style output

### Database Design Choices
- One avatar per user limit (can be replaced)
- Soft delete pattern with is_active flag for future multi-avatar support
- Foreign key constraints for data integrity
- Indexed fields for query performance

## Questions Answered
1. **File limits**: 10MB max, all image formats supported
2. **Avatar management**: Users can replace/update but only one active avatar
3. **GPT-4 Vision prompt**: Two-stage process for better comic-style results
4. **Future story integration**: Avatar data is stored and ready for use in story generation

## Testing Required
1. Test avatar upload with various image formats
2. Verify GPT-4 Vision and DALL-E integration
3. Test form validation and error handling
4. Verify navigation and responsive design
5. Test authentication flow and permissions

## Issues Found and Fixed

### Authentication Issue (2025-06-26)
**Problem**: Avatar endpoints returned 401 Unauthorized errors during testing
**Root Cause**: Used FastAPI dependency injection `get_current_user(req)` instead of manual token parsing
**Solution**: Updated all avatar endpoints to use manual header parsing pattern like existing `/my-stories` endpoint
**Files Changed**: main.py (avatar endpoints authentication logic)

### Dev Script Improvements (2025-06-26)
**Problem**: Health check failing due to insufficient wait time for container initialization  
**Solution**: Added robust retry mechanism with 10 attempts and 2-second intervals (up to 20 seconds total wait)
**Files Changed**: dev-local.sh (improved health check logic and added avatar endpoint documentation)

## Ready for Deployment
- All backend endpoints implemented and follow existing patterns
- Frontend component integrated with existing navigation
- Database schema added to migration system
- S3 storage follows existing architecture
- Authentication uses existing JWT system with manual token parsing
- Authentication issue resolved and tested