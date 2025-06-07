# My Story Buddy Backend

A FastAPI backend service for generating custom stories using OpenAI's GPT model. The service is deployed on AWS Lambda with API Gateway.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

4. Run locally:
   ```bash
   uvicorn main:app --reload
   ```

## Deployment

The backend is deployed on AWS Lambda with API Gateway. To deploy:

1. Build the deployment package:
   ```bash
   ./build.sh
   ```

2. Upload the generated `deployment.zip` to AWS Lambda.

3. Configure the Lambda function:
   - Set the handler to `lambda_function.lambda_handler`
   - Set the timeout to 30 seconds
   - Add the `OPENAI_API_KEY` environment variable

## API Endpoints

- `POST /generateStory`: Generate a story based on the provided prompt
  ```json
  {
    "prompt": "A story about a robot in space"
  }
  ```

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key

## License

MIT 