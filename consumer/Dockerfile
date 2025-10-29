FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY consumer/requirements.txt /app/consumer/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/consumer/requirements.txt

# Copy common module
COPY common/ /app/common/

# Copy consumer code
COPY consumer/ /app/consumer/

# Set Python path
ENV PYTHONPATH=/app

# Run the consumer worker
CMD ["python", "-m", "consumer.worker"]

