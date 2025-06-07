import json
import logging
from main import handler

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract the request body
        if event.get('body'):
            try:
                body = json.loads(event['body'])
                logger.info(f"Request body: {json.dumps(body)}")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing request body: {str(e)}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid JSON in request body'})
                }
        
        # Process the request
        logger.info("Processing request with FastAPI handler")
        response = handler(event, context)
        logger.info(f"Response from FastAPI: {json.dumps(response)}")
        
        return response
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        } 