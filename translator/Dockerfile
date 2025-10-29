FROM python:3.14-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY translator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common and translator code
COPY common/ /app/common/
COPY translator/ /app/translator/

# Set Python path to include /app
ENV PYTHONPATH=/app

# Set working directory to translator
WORKDIR /app/translator

# Run the worker
CMD ["python", "worker.py"]
