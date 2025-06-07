FROM public.ecr.aws/lambda/python:3.11

# Install zip
RUN yum install -y zip

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT}

# Copy all backend code
COPY main.py ${LAMBDA_TASK_ROOT}/
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/

# Create deployment package
RUN cd ${LAMBDA_TASK_ROOT} && \
    zip -r /tmp/deployment.zip . -x "*.pyc" -x "__pycache__/*"

# The deployment package will be available at /tmp/deployment.zip 