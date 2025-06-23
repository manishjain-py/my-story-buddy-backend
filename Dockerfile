FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Install system dependencies
RUN yum update -y && yum install -y \
    zip \
    gcc \
    && yum clean all

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT}

# Copy all backend code
COPY main.py ${LAMBDA_TASK_ROOT}/
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD ["lambda_function.lambda_handler"] 