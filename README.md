# My Story Buddy Backend

A FastAPI backend for generating stories using OpenAI's GPT model.

## Development

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn main:app --reload
```

## Deployment

The application is automatically deployed to AWS Lambda when changes are pushed to the main branch.

### Setting up GitHub Actions

To enable automated deployments, you need to set up the following secrets in your GitHub repository:

1. Go to your repository settings
2. Navigate to "Secrets and variables" > "Actions"
3. Add the following secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key
   - `LAMBDA_FUNCTION_NAME`: Your AWS Lambda function name (e.g., "my-story-buddy-backend")

### Required AWS Permissions

The AWS user needs the following permissions:
- `lambda:UpdateFunctionCode`
- `lambda:GetFunction`

Example IAM policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:UpdateFunctionCode",
                "lambda:GetFunction"
            ],
            "Resource": "arn:aws:lambda:us-west-2:*:function:my-story-buddy-backend"
        }
    ]
}
```

## Manual Deployment

If you need to deploy manually:

```bash
# Create deployment package
mkdir -p deployment
cp main.py deployment/
cp requirements.txt deployment/
cd deployment
pip install -r requirements.txt -t .
zip -r ../deployment.zip .

# Deploy to Lambda
aws lambda update-function-code \
  --function-name my-story-buddy-backend \
  --zip-file fileb://deployment.zip
```

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key
- `AWS_REGION`: AWS region (default: us-west-2)

## API Endpoints

- `POST /generateStory`: Generate a story based on the provided prompt
  - Request body: `{ "prompt": "string" }`
  - Response: `{ "title": "string", "story": "string" }`

## License

MIT # Testing automated deployment with SSH key configured
# Fixed EC2_HOST secret for deployment
