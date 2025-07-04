# Backend Setup Instructions

## Prerequisites
- Docker
- OpenAI API Key

## Quick Start

1. **Clone repository**
   ```bash
   git clone https://github.com/manishjain-py/my-story-buddy-backend.git
   cd my-story-buddy-backend
   ```

2. **Set OpenAI API key** (required)
   ```bash
   export OPENAI_API_KEY="your-openai-api-key-here"
   ```

3. **Run with Docker**
   ```bash
   ./dev-local.sh
   ```

4. **Test it works**
   ```bash
   curl http://localhost:8003/health
   ```
   Should return: `{"status":"healthy"...}`

## Optional: AWS Setup
For full functionality (image uploads), configure AWS:

**Option 1:** AWS CLI (recommended)
```bash
aws configure
```

**Option 2:** Environment variables
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

## Notes
- Backend runs at `http://localhost:8003`
- Works without AWS (images just won't upload to S3)
- Production deploys automatically via GitHub Actions