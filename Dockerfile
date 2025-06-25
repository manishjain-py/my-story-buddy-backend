FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy application code
COPY main.py ${LAMBDA_TASK_ROOT}/
COPY auth_routes.py ${LAMBDA_TASK_ROOT}/
COPY auth_models.py ${LAMBDA_TASK_ROOT}/
COPY auth_utils.py ${LAMBDA_TASK_ROOT}/
COPY database.py ${LAMBDA_TASK_ROOT}/
COPY email_service.py ${LAMBDA_TASK_ROOT}/

# Set the CMD to the Mangum handler directly from main.py
CMD ["main.handler"] 